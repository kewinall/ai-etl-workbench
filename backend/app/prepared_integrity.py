"""Last-use checks for private prepared files; never grants execution authority."""
from hashlib import sha256
from pathlib import Path
import re
import stat
from .source_binding import source_set_checksum


def verify_prepared_files(prepared):
    """Caller must still reserve authorization and mount files read-only.

    This detects changed bytes, missing files and redirected paths. It is not
    protection against an administrator modifying files after verification.
    Returns only checksums, never private paths or source content.
    """
    try:
        directory = Path(prepared['directory'])
        binding = prepared['binding']
        if not directory.is_absolute():
            raise ValueError()
        for ancestor in (directory, *directory.parents):
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError()
        result = {}
        source_format = binding.get('source_format', 'CSV')
        if 'source_format' in binding:
            if source_format not in ('XLSX', 'JSON') or 'source_checksums' in binding:
                raise ValueError()
            result['source_format'] = source_format
        if source_format != 'JSON' and ('json_reader' in binding or 'original_source_path' in prepared):
            raise ValueError()
        if 'source_checksums' in binding:
            checksums = binding['source_checksums']
            if source_set_checksum(checksums) != binding['source_checksum'] or 'source_path' in prepared:
                raise ValueError()
            paths = prepared['source_paths']
            if set(paths) != set(checksums):
                raise ValueError()
            files = [(paths[ref], f'source-{index}/source.csv', checksums[ref], ref)
                     for index,ref in enumerate(('source.0','source.1'))]
            result.update(source_checksums=checksums, source_checksum=binding['source_checksum'])
        else:
            if 'source_paths' in prepared:
                raise ValueError()
            if source_format == 'JSON':
                from .json_execution_binding import validate_reader_binding
                reader = validate_reader_binding(binding)
                result.update(source_checksum=binding['source_checksum'], json_reader=reader)
                files = [(prepared['source_path'], 'source.json', reader['reader_checksum'], 'reader_checksum'),
                         (prepared['original_source_path'], 'source-original.json', binding['source_checksum'], 'source_checksum')]
            else:
                files = [(prepared['source_path'], 'source.xlsx' if source_format == 'XLSX' else 'source.csv', binding['source_checksum'], 'source_checksum')]
        files.append((prepared['hpl_path'], 'candidate.hpl', binding['hpl_checksum'], 'hpl_checksum'))
        for raw_path, name, expected, checksum_key in files:
            path = Path(raw_path)
            if path != directory / name or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                raise ValueError()
            for ancestor in path.parents:
                info = ancestor.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError()
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError()
            digest = sha256()
            total = 0
            with path.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > 50 * 1024 * 1024:
                        raise ValueError()
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError()
            if checksum_key not in ('source.0', 'source.1'):
                result[checksum_key] = expected
        if source_format == 'JSON':
            original = Path(prepared['original_source_path']).read_bytes()
            content = Path(prepared['source_path']).read_bytes()
            has_bom = original.startswith(b'\xef\xbb\xbf')
            if (len(original) != reader['original_byte_count'] or len(content) != reader['reader_byte_count']
                    or reader['normalization'] != ('UTF8_BOM_REMOVED' if has_bom else 'NONE')
                    or content != (original[3:] if has_bom else original)):
                raise ValueError()
        return result
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('PREPARED_FILES_CHANGED_OR_UNAVAILABLE') from None

"""Deployment dependency versions, independently checked against installed metadata."""
import importlib.metadata
import os
from pathlib import Path
import re

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BACKEND = Path(__file__).resolve().parents[1]


def locked_versions():
    pins = {}
    for line in (BACKEND / 'constraints-linux-py312.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        assert re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+', line), line
        name, version = line.split('==')
        name = canonicalize_name(name)
        assert name not in pins, name
        pins[name] = version
    return pins


def test_direct_requirements_have_compatible_exact_constraints():
    pins = locked_versions()
    for line in (BACKEND / 'requirements.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        requirement = Requirement(line)
        name = canonicalize_name(requirement.name)
        assert name in pins, name
        assert pins[name] in requirement.specifier, name


@pytest.mark.skipif(os.getenv('WORKBENCH_VERIFY_DEPENDENCY_LOCK') != '1',
                    reason='Explicit Linux CPython 3.12 deployment environment required')
def test_installed_deployment_matches_constraints_and_dependency_closure():
    pins = locked_versions()
    for name, version in pins.items():
        assert importlib.metadata.version(name) == version, name
        for text in importlib.metadata.requires(name) or []:
            requirement = Requirement(text)
            if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
                continue
            dependency = canonicalize_name(requirement.name)
            assert dependency in pins, (name, dependency)
            assert pins[dependency] in requirement.specifier, (name, dependency)

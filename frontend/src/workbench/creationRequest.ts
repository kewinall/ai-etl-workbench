// Keep only the current in-memory draft; never persist source metadata in storage.
export class CreationRequest {
  private content='';
  private key='';
  private generate:()=>string;
  constructor(generate:()=>string=()=>crypto.randomUUID()){this.generate=generate}
  bind(payload:Record<string,unknown>){
    const content=JSON.stringify(payload);
    if(content!==this.content||!this.key){this.content=content;this.key=this.generate()}
    return {...payload,creation_request_key:this.key};
  }
}

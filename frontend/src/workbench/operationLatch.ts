// Synchronous admission control, before React can render a disabled button.
export class OperationLatch {
  private active=false;
  acquire(){if(this.active)return false;this.active=true;return true}
  release(){this.active=false}
}

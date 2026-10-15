export type UpdatePhase = 'idle'|'checking'|'available'|'current'|'unpublished'|'downloading'|'verifying'|'ready'|'installing'|'cancelled'|'error'|'installed'|'rolled_back';
export type UpdateState = {phase:UpdatePhase;tag?:string;message:string;received?:number;total?:number;canInstall?:boolean};
export type UpdateResult = {status:'available'|'current'|'unpublished';tag?:string;message:string;canInstall?:boolean};

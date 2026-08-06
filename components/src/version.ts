declare const __TEMBA_COMPONENTS_VERSION__: string;

let _version = 'dev';
try {
  _version = __TEMBA_COMPONENTS_VERSION__;
} catch {
  // not replaced by build tooling; keep default
}

export const TEMBA_COMPONENTS_VERSION = _version;

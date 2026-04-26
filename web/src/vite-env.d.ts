/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NAMING_API_BASE_URL?: string;
  readonly VITE_ENTRA_TENANT_ID?: string;
  readonly VITE_ENTRA_CLIENT_ID?: string;
  readonly VITE_NAMING_API_CLIENT_ID?: string;
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

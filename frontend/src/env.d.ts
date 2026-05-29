declare module "*.vue" {
  import type { DefineComponent } from "vue";

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
  export default component;
}

declare module "katex" {
  export interface KatexOptions {
    [key: string]: unknown;
  }

  const katex: {
    renderToString: (value: string, options?: KatexOptions) => string;
  };
  export default katex;
}

// Lets plain `node` run the repo's TypeScript: Node strips the types, and this hook resolves the
// extensionless imports (`./schema`, `../validate`) the sources use for the bundler.
import { registerHooks } from "node:module";
import { existsSync } from "node:fs";
import { URL, fileURLToPath } from "node:url";

registerHooks({
  resolve(specifier, context, nextResolve) {
    if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL) {
      const base = new URL(specifier, context.parentURL);
      for (const suffix of [".ts", "/index.ts"]) {
        const candidate = new URL(base.href + suffix);
        if (existsSync(fileURLToPath(candidate))) return nextResolve(candidate.href, context);
      }
    }
    return nextResolve(specifier, context);
  },
});

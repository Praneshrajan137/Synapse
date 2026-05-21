// SYNAPSE Atlas Console — ESLint flat config (ESLint 9).
//
// Layered rules: language → React → a11y → import hygiene → vitest → storybook.
// Generated artifacts (Orval, route tree, Zod) are excluded; CODEOWNERS keeps
// hand-written imports honest.
//
// The `no-restricted-syntax` rule blocks two foot-guns:
//   1. Bare `JSON.stringify(body)` for /a2a or /api/v1/decisions calls — the
//      project mandates canonical (sorted-key) JSON for KV-cache stability
//      (I-13). Use canonicalize() from @shared/canonical-json instead.
//   2. Cross-surface imports — surfaces are bounded contexts; talk via
//      @shared/* anti-corruption layers only.

import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import jsxA11y from "eslint-plugin-jsx-a11y";
import importX from "eslint-plugin-import-x";
import vitest from "eslint-plugin-vitest";
import storybook from "eslint-plugin-storybook";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  {
    ignores: [
      "dist",
      "storybook-static",
      "playwright-report",
      "test-results",
      "coverage",
      ".lighthouseci",
      "src/routeTree.gen.ts",
      "src/shared/api/__generated__",
      "src/shared/schemas/__generated__",
      "*.config.{js,cjs,mjs}",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    files: ["src/**/*.{ts,tsx,js,jsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.browser, ...globals.es2023 },
      parser: tseslint.parser,
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      "jsx-a11y": jsxA11y,
      "import-x": importX,
    },
    settings: { react: { version: "18.3" } },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.strict.rules,

      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "react/prop-types": "off",

      // Boundary discipline.
      "import-x/no-cycle": "error",
      "import-x/no-self-import": "error",
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "CallExpression[callee.object.name='JSON'][callee.property.name='stringify']:has(Literal[value=/\\\\/a2a|\\\\/api\\\\/v1\\\\/decisions/])",
          message:
            "Use canonicalize() from @shared/canonical-json for /a2a and /api/v1/decisions payloads (I-13 KV-cache stability).",
        },
      ],
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@surfaces/*/*", "../../surfaces/*"],
              message:
                "Cross-surface imports forbidden — bounded contexts talk via @shared/* anti-corruption layers (plan §6).",
            },
          ],
        },
      ],

      // Type strictness.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" },
      ],
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
    },
  },
  {
    files: ["src/**/*.{test,spec}.{ts,tsx}", "src/shared/test/**/*.{ts,tsx}"],
    plugins: { vitest },
    rules: { ...vitest.configs.recommended.rules },
  },
  {
    files: ["src/**/*.stories.{ts,tsx}", ".storybook/**/*.{ts,tsx}"],
    plugins: { storybook },
    rules: { ...storybook.configs.recommended.rules },
  },
  prettier,
);

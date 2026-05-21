/* SYNAPSE Atlas Console — i18next-parser.
 *
 * Extracts translation keys at build time from src/**\/*.{ts,tsx}.
 * CI runs this in dry-run mode and fails if any locale is missing keys
 * the source code references — see frontend.yml.
 */
module.exports = {
  contextSeparator: "_",
  createOldCatalogs: false,
  defaultNamespace: "translation",
  defaultValue: "",
  indentation: 2,
  keepRemoved: false,
  keySeparator: ".",
  lexers: {
    js: ["JavascriptLexer"],
    ts: ["JavascriptLexer"],
    jsx: ["JsxLexer"],
    tsx: ["JsxLexer"],
    default: ["JavascriptLexer"],
  },
  lineEnding: "auto",
  locales: ["en-IN", "hi-IN", "kn-IN", "mr-IN"],
  namespaceSeparator: ":",
  output: "src/shared/i18n/locales/$LOCALE.json",
  pluralSeparator: "_",
  input: ["src/**/*.{ts,tsx}"],
  sort: true,
  verbose: false,
  failOnWarnings: false,
  failOnUpdate: false,
};

import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    files: ["static/js/**/*.js", "static/**/*.html"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        requestAnimationFrame: "readonly",
        cancelAnimationFrame: "readonly",
        fetch: "readonly",
        AbortController: "readonly",
        AbortSignal: "readonly",
        TextDecoder: "readonly",
        Date: "readonly",
        JSON: "readonly",
        Math: "readonly",
        parseInt: "readonly",
        isNaN: "readonly",
        localStorage: "readonly",
        HTMLElement: "readonly",
        Node: "readonly",
        Event: "readonly",
        Promise: "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-undef": "error",
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-constant-condition": "warn",
      "no-inner-declarations": "off",
      "no-redeclare": "off",
      "no-useless-escape": "warn",
      "prefer-const": "off",
      "no-var": "off",
    },
  },
  {
    files: ["static/**/*.html"],
    rules: {
      "no-undef": "off",
    },
  },
];

import js from "@eslint/js";
import html from "eslint-plugin-html";

export default [
  js.configs.recommended,
  {
    plugins: {
      html,
    },
  },
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

      "no-restricted-syntax": [
        "error",
        {
          selector: "AssignmentExpression[left.property.name='innerHTML'][right.value!='']",
          message: "禁止直接赋值 innerHTML（非清空）。请使用 HtmlUtils.setSafeHtml()、HtmlUtils.setTrustedHtml() 或 DOM API（createElement + textContent）。"
        },
        {
          selector: "Literal[value=/https?:\\/\\/localhost/]",
          message: "禁止硬编码 localhost URL。请使用 App.BACKEND_URL 或 App.API。"
        },
        {
          selector: "Literal[value=/127\\.0\\.0\\.1/]",
          message: "禁止硬编码 127.0.0.1。请使用 App.BACKEND_URL 或 App.API。"
        }
      ],
    },
  },
  {
    files: ["static/**/*.html"],
    rules: {
      "no-undef": "off",
      "no-restricted-syntax": "off",
    },
  },
];

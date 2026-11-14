// Configuración de ESLint: Google TypeScript Style Guide con los ajustes de la
// cátedra (CLAUDE.md): 2 espacios, llaves Allman y largo máximo de 180.
// No se usa Prettier porque no admite llaves Allman.
import js from '@eslint/js';
import stylistic from '@stylistic/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

const MAX_LINE_LENGTH = 180;
const INDENT_SPACES = 2;

const styleRules = {
  '@stylistic/brace-style': ['error', 'allman', {allowSingleLine: false}],
  '@stylistic/indent': ['error', INDENT_SPACES, {SwitchCase: 1}],
  '@stylistic/max-len': ['error', {code: MAX_LINE_LENGTH, ignoreUrls: true, ignoreStrings: true, ignoreTemplateLiterals: true}],
  '@stylistic/no-tabs': 'error',
  '@stylistic/quotes': ['error', 'single', {avoidEscape: true}],
  '@stylistic/semi': ['error', 'always'],
  '@stylistic/comma-dangle': ['error', 'always-multiline'],
  '@stylistic/object-curly-spacing': ['error', 'never'],
  '@stylistic/eol-last': 'error',
  '@stylistic/no-trailing-spaces': 'error',
  '@stylistic/jsx-indent-props': ['error', INDENT_SPACES],
};

// Reglas de la guía de Google: llaves siempre, sin var, sin export default,
// comparaciones estrictas y nombres según el tipo de identificador.
const googleRules = {
  'curly': ['error', 'all'],
  'eqeqeq': ['error', 'always'],
  'no-var': 'error',
  'prefer-const': 'error',
  'no-restricted-syntax': ['error', {selector: 'ExportDefaultDeclaration', message: 'La guía de Google pide exports con nombre.'}],
  '@typescript-eslint/explicit-function-return-type': ['error', {allowExpressions: true, allowTypedFunctionExpressions: true}],
  '@typescript-eslint/naming-convention': [
    'error',
    {selector: 'typeLike', format: ['PascalCase']},
    {selector: 'variable', format: ['camelCase', 'UPPER_CASE', 'PascalCase']},
    {selector: 'function', format: ['camelCase', 'PascalCase']},
    {selector: 'parameter', format: ['camelCase'], leadingUnderscore: 'allow'},
  ],
};

export default tseslint.config(
  {ignores: ['dist', 'node_modules']},
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx,js}'],
    languageOptions: {ecmaVersion: 2022, globals: {...globals.browser, ...globals.node}},
    plugins: {'@stylistic': stylistic, 'react-hooks': reactHooks},
    rules: {...styleRules, ...googleRules, ...reactHooks.configs.recommended.rules},
  },
  {
    // Los archivos de configuración de las herramientas exigen export default.
    files: ['vite.config.ts', 'eslint.config.js'],
    rules: {'no-restricted-syntax': 'off'},
  },
);

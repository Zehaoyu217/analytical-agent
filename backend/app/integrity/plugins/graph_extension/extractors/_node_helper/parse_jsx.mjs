#!/usr/bin/env node
/**
 * Reads a JSON list of file paths from stdin.
 * For each, parses with @babel/parser (jsx + typescript plugins) and emits
 * one record per usage edge. Output: JSON to stdout.
 *
 * Schema:
 *   [{file, edges: [{source, target, kind, line}], errors: [string]}]
 */
import { readFileSync } from 'node:fs';
import { resolve, dirname, basename, extname } from 'node:path';
import { parse } from '@babel/parser';
import traverseModule from '@babel/traverse';

const traverse = traverseModule.default ?? traverseModule;

const HOC_NAMES = new Set([
  'withRouter', 'withTranslation', 'withStyles', 'withTheme', 'connect', 'observer', 'memo', 'forwardRef',
]);

function readStdin() {
  return readFileSync(0, 'utf-8');
}

function parseFile(filePath) {
  const code = readFileSync(filePath, 'utf-8');
  return parse(code, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript', 'decorators-legacy'],
    errorRecovery: true,
  });
}

function fileToComponentName(filePath) {
  const base = basename(filePath, extname(filePath));
  return base;
}

function getEnclosingDeclName(path) {
  let cur = path.parentPath;
  while (cur) {
    if (cur.isFunctionDeclaration() && cur.node.id) return cur.node.id.name;
    if (cur.isVariableDeclarator() && cur.node.id?.name) return cur.node.id.name;
    if (cur.isClassDeclaration() && cur.node.id) return cur.node.id.name;
    if (cur.isExportDefaultDeclaration()) return 'default';
    cur = cur.parentPath;
  }
  return null;
}

function jsxOpeningName(node) {
  // <Foo /> → 'Foo'   <Foo.Bar /> → 'Foo.Bar'
  let n = node.name;
  if (n.type === 'JSXIdentifier') return n.name;
  if (n.type === 'JSXMemberExpression') {
    const parts = [];
    while (n.type === 'JSXMemberExpression') {
      parts.unshift(n.property.name);
      n = n.object;
    }
    if (n.type === 'JSXIdentifier') parts.unshift(n.name);
    return parts.join('.');
  }
  return null;
}

function isComponent(name) {
  if (!name) return false;
  // Components start with uppercase or contain a `.` (member exprs)
  return /^[A-Z]/.test(name.split('.')[0]);
}

function unwrapHOC(node) {
  // withFoo(MyComp) → MyComp
  // connect(state)(MyComp) → MyComp
  // memo(forwardRef(MyComp)) → MyComp
  let cur = node;
  while (cur && cur.type === 'CallExpression') {
    const callee = cur.callee;
    if (callee.type === 'Identifier' && HOC_NAMES.has(callee.name)) {
      // find first identifier-like arg
      const arg = cur.arguments.find(a => a.type === 'Identifier' || a.type === 'CallExpression');
      if (!arg) return null;
      if (arg.type === 'Identifier') return arg.name;
      cur = arg;
      continue;
    }
    if (callee.type === 'CallExpression') {
      // connect(state)(MyComp) — callee itself is a call returning HOC
      const arg = cur.arguments.find(a => a.type === 'Identifier');
      return arg ? arg.name : null;
    }
    return null;
  }
  return null;
}

function extractEdges(filePath) {
  const out = { file: filePath, edges: [], errors: [] };
  let ast;
  try {
    ast = parseFile(filePath);
  } catch (e) {
    out.errors.push(String(e.message ?? e));
    return out;
  }

  const fileComp = fileToComponentName(filePath);

  traverse(ast, {
    JSXOpeningElement(path) {
      const target = jsxOpeningName(path.node);
      if (!isComponent(target)) return;
      const enc = getEnclosingDeclName(path) ?? fileComp;
      out.edges.push({
        source: enc,
        target: target.split('.')[0],
        kind: 'direct',
        line: path.node.loc?.start?.line ?? null,
      });
    },
    VariableDeclarator(path) {
      const init = path.node.init;
      if (!init || init.type !== 'CallExpression') return;
      if (init.callee.type !== 'Identifier' || init.callee.name !== 'lazy') return;
      const arrow = init.arguments[0];
      if (!arrow || (arrow.type !== 'ArrowFunctionExpression' && arrow.type !== 'FunctionExpression')) return;
      const body = arrow.body;
      const importCall = body.type === 'CallExpression' ? body :
        (body.type === 'BlockStatement' ? null : null);
      if (!importCall || importCall.callee.type !== 'Import') return;
      const arg = importCall.arguments[0];
      if (arg?.type !== 'StringLiteral') return;
      const lazyName = path.node.id?.name;
      if (!lazyName) return;
      const importedBase = arg.value.split('/').pop();
      out.edges.push({
        source: lazyName,
        target: importedBase,
        kind: 'lazy',
        line: path.node.loc?.start?.line ?? null,
      });
    },
    ExportDefaultDeclaration(path) {
      const decl = path.node.declaration;
      if (decl?.type === 'CallExpression') {
        const inner = unwrapHOC(decl);
        if (inner) {
          out.edges.push({
            source: 'default',
            target: inner,
            kind: 'hoc',
            line: path.node.loc?.start?.line ?? null,
          });
        }
      }
    },
  });

  return out;
}

function main() {
  const raw = readStdin();
  let files;
  try {
    files = JSON.parse(raw);
  } catch (e) {
    process.stderr.write(`bad stdin JSON: ${e}\n`);
    process.exit(2);
  }
  const out = files.map(extractEdges);
  process.stdout.write(JSON.stringify(out));
}

main();

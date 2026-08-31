/**
 * Scout an unknown TypeScript repo. Same algorithm as the Python one: an import
 * edge runs to whatever file *defines* the imported name and never to the file
 * the specifier names — so a re-export barrel scores nothing and the file that
 * actually defines the name takes the whole score. Where several files define
 * one name the specifier picks between them, and only there.
 *
 * No dependency of its own: it loads `typescript` out of the target repo's own
 * node_modules, on the same reasoning that the Python scout uses the stdlib
 * `ast` — a TS repo already requires the TS compiler, so using it adds nothing.
 *
 * Every edge weighs the same. The three weight heuristics that stood here were a
 * port of aider's, and measured over three repositories they changed at most one
 * top-20 entry in twenty on a real project tree: a multiplier applied to most
 * edges cancels, because every edge is divided by its source's outgoing count.
 */

import { createRequire, builtinModules } from "node:module";
import fs from "node:fs";
import path from "node:path";

const DAMPING = 0.85;
// The iteration runs until the ranking stops moving: total movement across all
// nodes below a threshold scaled to one node's share of the ranking, 1/n.
const TOLERANCE = 1e-6;
// A safety limit and not a tuning parameter — it bounds a graph that never
// settles, and cannot change a ranking that has already converged.
const MAX_ITERATIONS = 200;
const SKIP = new Set([".git", ".next", ".turbo"]);

// Same linguist-derived list the Python scout uses, for the same measured reason.
const VENDORED = /(^|\/)(vendors?|(3rd|third)[-_]?party|node_modules|bower_components|dist|build|out|coverage|testdata|tests?\/fixtures)(\/|$)/i;
const GENERATED = /(\.generated\.tsx?|\.pb\.ts)$/;
const EXTS = [".ts", ".tsx", ".mts", ".cts"];

// A network mount that times out mid-walk took down a whole run — the failure
// mode core/scripts/scout.py:84-86 documents. One bad directory costs that
// directory, not the scan; the caller learns via hadError rather than a
// swallowed exit 0, because cli/flw.py only inspects returncode 2.
function sources(root) {
  const out = [];
  let hadError = false;
  (function walk(dir) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (err) {
      console.error(`warning: skipping unreadable directory ${dir} (${err.message})`);
      hadError = true;
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".") || SKIP.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      const rel = path.relative(root, full);
      if (VENDORED.test(rel)) continue;
      if (entry.isDirectory()) walk(full);
      else if (EXTS.some((e) => entry.name.endsWith(e)) && !entry.name.endsWith(".d.ts") && !GENERATED.test(rel)) out.push(full);
    }
  })(root);
  return { files: out, hadError };
}

// A package is a directory that declares itself one. `parts[0]` reported every
// service of a monorepo as a single node named after the directory holding them.
// The repository root is not a candidate: a package.json there says the repo is
// a package, not where the boundaries inside it fall.
const PACKAGE_MARKERS = ["__init__.py", "pyproject.toml", "package.json"];

function packageOf(root, file, cache) {
  let here = path.dirname(file);
  const walked = [];
  let found = null;
  while (here !== root) {
    if (cache.has(here)) { found = cache.get(here); break; }
    if (PACKAGE_MARKERS.some((m) => fs.existsSync(path.join(here, m)))) {
      found = path.relative(root, here);
      break;
    }
    walked.push(here);
    here = path.dirname(here);
  }
  if (found === null) {
    // A tree with no markers still has directories.
    const parts = path.relative(root, file).split(path.sep);
    found = parts.length > 1 ? parts[0] : ".";
  }
  for (const seen of walked) cache.set(seen, found);
  return found;
}

// Strongly connected components, Tarjan, iterative — a deep package graph would
// otherwise hit the recursion limit.
function components(graph) {
  const index = new Map(), low = new Map(), on = new Set();
  const stack = [], found = [];
  let counter = 0;
  for (const start of graph.keys()) {
    if (index.has(start)) continue;
    index.set(start, counter); low.set(start, counter); counter++;
    stack.push(start); on.add(start);
    const work = [[start, (graph.get(start) ?? new Set()).values()]];
    while (work.length) {
      const [node, kids] = work[work.length - 1];
      let descended = false;
      for (const kid of kids) {
        if (!index.has(kid)) {
          index.set(kid, counter); low.set(kid, counter); counter++;
          stack.push(kid); on.add(kid);
          work.push([kid, (graph.get(kid) ?? new Set()).values()]);
          descended = true;
          break;
        }
        if (on.has(kid)) low.set(node, Math.min(low.get(node), index.get(kid)));
      }
      if (descended) continue;
      work.pop();
      if (work.length) {
        const up = work[work.length - 1][0];
        low.set(up, Math.min(low.get(up), low.get(node)));
      }
      if (low.get(node) === index.get(node)) {
        const group = [];
        for (;;) {
          const top = stack.pop();
          on.delete(top);
          group.push(top);
          if (top === node) break;
        }
        found.push(group);
      }
    }
  }
  return found;
}

const isTest = (p) => /(^|\/)(tests?|__tests__)\//.test(p) || /\.(test|spec)\.[cm]?tsx?$/.test(p);

// tsconfig `paths` is how a bare specifier names this repo's own files. Read
// through the compiler already loaded, because the file is JSON with comments.
function readAliases(root, ts) {
  const file = path.join(root, "tsconfig.json");
  if (!fs.existsSync(file)) return { base: root, rules: [] };
  const { config, error } = ts.readConfigFile(file, (f) => fs.readFileSync(f, "utf8"));
  const options = (!error && config && config.compilerOptions) || {};
  return {
    base: path.resolve(root, options.baseUrl ?? "."),
    rules: Object.entries(options.paths ?? {}).map(([from, to]) => [from, [].concat(to)]),
  };
}

// A `paths` pattern carries at most one `*`, and what it matched is substituted
// into each of its targets. `@/lib/types` against `@/*` -> `src/*` is baseUrl
// plus `src/lib/types`; without this it resolves to nothing and `@/lib` is
// counted as a third-party package the project depends on.
function aliasTargets(spec, aliases) {
  const found = [];
  for (const [from, to] of aliases.rules) {
    const star = from.indexOf("*");
    let tail;
    if (star < 0) {
      if (spec !== from) continue;
      tail = "";
    } else {
      const head = from.slice(0, star);
      const rest = from.slice(star + 1);
      if (spec.length < head.length + rest.length) continue;
      if (!spec.startsWith(head) || !spec.endsWith(rest)) continue;
      tail = spec.slice(head.length, spec.length - rest.length);
    }
    for (const one of to) found.push(path.resolve(aliases.base, one.replace("*", tail)));
  }
  return found;
}

// A specifier names a module, never a definition. Resolving it is what lets an
// import that carries no definition name — a namespace import, a side-effect
// import, a name this repo never defines — become an edge at all; named imports
// still resolve through `definers`, so a barrel takes none of the score.
function resolveSpec(spec, fromFile, root, topDirs, fileSet, aliases) {
  const bases = [];
  if (spec.startsWith(".")) bases.push(path.resolve(path.dirname(fromFile), spec));
  else {
    bases.push(...aliasTargets(spec, aliases));
    if (topDirs.has(spec.split("/")[0])) bases.push(path.resolve(root, spec));
  }
  for (const candidate of bases) {
    // NodeNext writes `./mod.js` for what on disk is `mod.ts`.
    const base = candidate.replace(/\.[cm]?js$/, "");
    for (const e of EXTS) if (fileSet.has(base + e)) return base + e;
    for (const e of EXTS) {
      const idx = path.join(base, "index" + e);
      if (fileSet.has(idx)) return idx;
    }
  }
  return null;
}

function main(root, budget) {
  root = path.resolve(root);
  const require = createRequire(path.join(root, "noop.js"));
  let ts;
  try {
    ts = require("typescript");
  } catch (err) {
    // The message ends in a "Require stack:" naming root/noop.js, a file that
    // does not exist — createRequire only needs a path to resolve from, so
    // printing it sends the reader looking for it. The remedy belongs to
    // cli/flw.py, which reads the lock file and so knows whether this repo
    // installs with npm, pnpm, yarn or bun.
    console.error(`error: no typescript in ${root}/node_modules (${err.message.split("\nRequire stack:")[0]})`);
    process.exit(2);
  }
  const major = Number(ts.version.split(".")[0]);
  if (major >= 7) {
    console.error(`error: typescript ${ts.version} found in ${root}/node_modules, but this scout needs the 5.x or 6.x compiler API. typescript 7 moved it under ./unstable/*.`);
    process.exit(2);
  }

  const { files, hadError } = sources(root);
  if (hadError) process.exitCode = 3;
  const defs = new Map();       // file -> [{name, line, sig}]
  const importsOf = new Map();  // file -> Map<name, Set of modules imported from>
  const specImports = new Map();// file -> [{names, target}]
  const externals = new Map();  // package -> count
  const fileSet = new Set(files);
  const rel = (f) => path.relative(root, f);

  // A bare specifier whose first segment names a top-level directory of this
  // repo is a tsconfig `paths` alias, not a third-party dependency.
  const topDirs = new Set(
    fs.readdirSync(root, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name),
  );
  const aliases = readAliases(root, ts);

  for (const file of files) {
    const src = ts.createSourceFile(
      file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true,
    );
    const here = [];
    const seen = new Map(); // name -> Set of modules it was imported from
    const specs = [];

    const line = (n) => src.getLineAndCharacterOfPosition(n.getStart(src)).line + 1;
    const exported = (n) =>
      n.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword);

    for (const node of src.statements) {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
        const spec = node.moduleSpecifier.text;
        const names = [];
        const bindings = node.importClause?.namedBindings;
        if (bindings && ts.isNamedImports(bindings)) {
          for (const el of bindings.elements) names.push(el.name.text);
        }
        if (node.importClause?.name) names.push(node.importClause.name.text);
        const target = resolveSpec(spec, file, root, topDirs, fileSet, aliases);
        // Each name remembers the modules it was imported from, because the
        // module is what tells two files exporting the same name apart.
        for (const name of names) {
          if (!seen.has(name)) seen.set(name, new Set());
          seen.get(name).add(target);
        }
        specs.push({ names, target });
        if (!spec.startsWith(".")) {
          const pkg = spec.startsWith("@") ? spec.split("/").slice(0, 2).join("/") : spec.split("/")[0];
          const builtin = spec.startsWith("node:") || builtinModules.includes(pkg);
          const aliased = aliasTargets(spec, aliases).length > 0;
          // Test dependencies are not what a project is built on. Counting them
          // puts a test runner at the top of the list and buries what the
          // product actually uses — the same measurement scout.py made.
          if (!builtin && !aliased && !topDirs.has(pkg) && !isTest(rel(file))) {
            externals.set(pkg, (externals.get(pkg) ?? 0) + 1);
          }
        }
      } else if (!exported(node)) {
        continue;
      } else if (ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node)) {
        if (node.name) here.push({ name: node.name.text, line: line(node), sig: "" });
      } else if (ts.isFunctionDeclaration(node)) {
        if (node.name) {
          const params = node.parameters.map((p) => p.name.getText(src)).join(", ");
          here.push({ name: node.name.text, line: line(node), sig: `(${params})` });
        }
      } else if (ts.isTypeAliasDeclaration(node) || ts.isEnumDeclaration(node)) {
        here.push({ name: node.name.text, line: line(node), sig: "" });
      } else if (ts.isVariableStatement(node)) {
        for (const d of node.declarationList.declarations) {
          if (ts.isIdentifier(d.name)) here.push({ name: d.name.text, line: line(node), sig: "" });
        }
      }
    }
    defs.set(file, here);
    importsOf.set(file, seen);
    specImports.set(file, specs);
  }

  const definers = new Map();
  for (const [file, here] of defs) {
    for (const d of here) {
      if (!definers.has(d.name)) definers.set(d.name, []);
      definers.get(d.name).push(file);
    }
  }

  // One edge per imported name that resolves, all weighing the same. A file
  // importing one local name and twenty from elsewhere gives that name the same
  // score as a file importing nothing else.
  const out = new Map();
  const importers = new Map(); // `${file}\0${name}` -> Set of importing files
  const incoming = new Map();
  const push = (src, dst) => {
    if (!out.has(src)) out.set(src, []);
    out.get(src).push(dst);
    incoming.set(dst, (incoming.get(dst) ?? 0) + 1);
  };
  for (const [src, seen] of importsOf) {
    for (const [name, targets] of seen) {
      const all = definers.get(name) ?? [];
      for (const target of targets) {
        // The definer in the module the import named, and every definer only
        // when none matches. The fallback is what keeps a re-export barrel
        // taking none of the score: a barrel exports nothing of its own, so
        // nothing matches there and the edge reaches the definition instead.
        for (const dst of target && all.includes(target) ? [target] : all) {
          if (dst === src) continue;
          push(src, dst);
          const key = `${dst}\0${name}`;
          if (!importers.has(key)) importers.set(key, new Set());
          importers.get(key).add(src);
        }
      }
    }
  }
  // A specifier import names no export, so it would rank a file and leave it
  // with nothing printed under it. Counted separately and shown as its own row,
  // in the same unit as an export's: how many files import this thing.
  const asModule = new Map(); // `${file}\0${stem}` -> Set of importing files
  for (const [src, recs] of specImports) {
    for (const { names, target } of recs) {
      if (!target || target === src) continue;
      if (names.length && names.some((n) => (definers.get(n) ?? []).length)) continue;
      push(src, target);
      const stem = path.basename(target).replace(/\.[cm]?tsx?$/, "");
      const key = `${target}\0${stem}`;
      if (!asModule.has(key)) asModule.set(key, new Set());
      asModule.get(key).add(src);
    }
  }

  // PageRank, power iteration, run until the ranking stops moving.
  const n = files.length;
  let rank = new Map(files.map((f) => [f, 1 / n]));
  for (let i = 0; i < MAX_ITERATIONS; i++) {
    const next = new Map(files.map((f) => [f, (1 - DAMPING) / n]));
    let dangling = 0;
    for (const file of files) {
      const edges = out.get(file);
      if (!edges || !edges.length) {
        dangling += rank.get(file); // spread evenly, once, below
        continue;
      }
      const share = (DAMPING * rank.get(file)) / edges.length;
      for (const dst of edges) next.set(dst, next.get(dst) + share);
    }
    if (dangling) {
      const spread = (DAMPING * dangling) / n;
      for (const f of files) next.set(f, next.get(f) + spread);
    }
    let moved = 0;
    for (const f of files) moved += Math.abs(next.get(f) - rank.get(f));
    rank = next;
    if (moved < TOLERANCE / n) break;
  }

  const named = new Map();
  for (const source of [importers, asModule]) {
    for (const [key, who] of source) {
      const cut = key.indexOf("\0");
      const file = key.slice(0, cut);
      if (!named.has(file)) named.set(file, []);
      named.get(file).push([key.slice(cut + 1), who.size]);
    }
  }

  const code = files.filter((f) => !isTest(rel(f)));
  const defCount = [...defs.values()].reduce((a, v) => a + v.length, 0);
  console.log(`${files.length} ts files (${files.length - code.length} test), ${defCount} exported definitions\n`);

  const cache = new Map();
  const packageOfFile = new Map(code.map((f) => [f, packageOf(root, f, cache)]));
  const packages = new Map();
  for (const f of code) {
    const key = packageOfFile.get(f);
    packages.set(key, (packages.get(key) ?? 0) + 1);
  }
  console.log("PACKAGES");
  for (const [d, c] of [...packages].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${d.padEnd(28)} ${String(c).padStart(3)} files`);
  }

  console.log("\nEXTERNAL DEPENDENCIES");
  for (const [pkg, c] of [...externals].sort((a, b) => b[1] - a[1]).slice(0, 8)) {
    console.log(`  ${pkg.padEnd(28)} ${String(c).padStart(3)} imports`);
  }

  // Who uses whom across packages, which the per-file ranking never states.
  const pkgEdges = new Map();
  for (const [src, dsts] of out) {
    const a = packageOfFile.get(src);
    if (a === undefined) continue;
    for (const dst of dsts) {
      const b = packageOfFile.get(dst);
      if (b === undefined || a === b) continue;
      const key = `${a}\0${b}`;
      pkgEdges.set(key, (pkgEdges.get(key) ?? 0) + 1);
    }
  }
  const plural = (n) => (n === 1 ? "" : "s");
  if (pkgEdges.size) {
    const ordered = [...pkgEdges]
      .map(([k, n]) => [...k.split("\0"), n])
      .sort((x, y) => y[2] - x[2] || (x[0] < y[0] ? -1 : 1));
    console.log("\nDEPENDS ON");
    for (const [a, b, n] of ordered.slice(0, 20)) {
      console.log(`  ${a} -> ${b}   ${n} import${plural(n)}`);
    }
    if (ordered.length > 20) {
      console.log(`  … ${ordered.length - 20} more package edges not shown`);
    }

    // Only components of two or more, and only between packages: the same
    // section at file level prints one giant component on any real repo.
    const graph = new Map();
    for (const [a, b] of ordered) {
      if (!graph.has(a)) graph.set(a, new Set());
      if (!graph.has(b)) graph.set(b, new Set());
      graph.get(a).add(b);
    }
    const cycles = components(graph).filter((g) => g.length > 1);
    if (cycles.length) {
      console.log("\nCYCLES");
      for (const group of cycles) {
        const members = [...group].sort();
        let shown = members.slice(0, 8).join(" <-> ");
        if (members.length > 8) shown += ` <-> … ${members.length - 8} more`;
        console.log(`  ${shown}`);
        const inside = ordered.filter(([a, b]) => group.includes(a) && group.includes(b));
        for (const [a, b, n] of inside.slice(0, 10)) {
          console.log(`      ${a} -> ${b}   ${n} import${plural(n)}`);
        }
        if (inside.length > 10) {
          console.log(`      … ${inside.length - 10} more edges inside this cycle`);
        }
      }
    }
  }

  // PageRank orders the files. Within a file the names are ordered by how many
  // files import each — a plain count, which needs no weights to be comparable.
  console.log("\nMOST IMPORTANT EXPORTS");
  const depended = files
    .filter((f) => (incoming.get(f) ?? 0) > 0 && !isTest(rel(f)))
    .sort((a, b) => rank.get(b) - rank.get(a));
  let printed = 0;
  for (const file of depended) {
    if (printed >= budget) break;
    console.log(`\n  ${rel(file)}   ${rank.get(file).toFixed(4)}`);
    printed++;
    const names = (named.get(file) ?? []).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
    for (const [name, count] of names.slice(0, 4)) {
      if (printed >= budget) break;
      const sig = defs.get(file)?.find((d) => d.name === name)?.sig ?? "";
      console.log(`      ${name}${sig}   ${count} file${count === 1 ? "" : "s"}`);
      printed++;
    }
  }
}

main(process.argv[2], Number(process.argv[3] ?? 20));

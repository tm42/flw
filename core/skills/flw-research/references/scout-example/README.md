# A scanner for a language flw ships none for

flw ships one scanner, for Python, and a contract a second one satisfies. `scout.mjs` beside this file is a working second instance, for TypeScript. It is reference material: nothing runs it, no check reads it, and no test covers it. Read it, then write your own.

## The contract

A scanner is an executable flw runs as:

```text
<scanner> <root> <budget>
```

`<root>` is an absolute path to the directory being ranked. `<budget>` is roughly how many lines of output to print, so a ranking fits a reply rather than filling one.

It prints **one finished ranking section** to stdout. Nothing is folded or re-ranked across languages: each scanner's section is the output, in the order the key lists them, after the built-in Python one. What to print is yours — `scout.mjs` mirrors the Python scanner's sections because the two are the same algorithm, and a scanner for a language whose structure is different should print what orients a reader in that language.

The exit code answers what flw cannot work out for a language it has never heard of:

- **0** — it ranked something.
- **1** — this repository holds no file of my language. Print one line saying so; the run carries on with whatever else ranked.
- **2** — the language's own parser is absent from this repository. Say what to install. flw cannot: it does not know the language, so it cannot read a lock file or name a package manager.
- **3** — it ranked, but could not read part of the tree. The section still prints, and the run says the ranking covers less than the tree.

Any other code is named on stderr as outside the contract, because silence there reads as a language with nothing in it.

Two conditions of the four are worth getting the order right on. When a repository holds no file of your language **and** no parser for it, exit 1: telling someone to install a compiler for a language they are not using is advice that costs them an install and changes nothing. `scout.mjs` walks before it loads the compiler for exactly that reason.

## Registering it

In the project's own flw config — `<project root>/.flw/config.toml`, never `~/.flw/config.toml`, because a scanner is a file in this repository:

```toml
[scout]
scanners = [
  { path = "tools/go-scout", extensions = [".go"] },
]
```

`path` is relative to the project root. An absolute path, or one holding `..`, is named on stderr and not run: the config file is checked in, and a path whose meaning depends on the machine is not.

`extensions` is every file suffix that scanner reads. It is declared rather than guessed because `flw scout` ends by saying what nothing parsed, and it subtracts each declared suffix from that count. Leave a suffix out and the run reports files your scanner has just ranked; flw cannot tell the difference.

The built-in Python scanner is never listed. The key **adds** scanners, so registering one never stops another language being ranked.

## What the scanner needs on disk

- A shebang on line 1 and the execute bit. flw runs it as a command, not through an interpreter it picks for you. A file without the execute bit is named on stderr and not run.
- No dependency flw installs. `scout.mjs` loads `typescript` out of the repository it is ranking, on the same reasoning that the Python scanner uses the stdlib `ast`: a repository in a language already holds that language's parser.

## Writing one

`flw scout` is orientation and it is regenerated on every run, so a scanner is allowed to be approximate. What it must not be is quietly wrong about its own coverage, which is what the suffix declaration and exit code 3 are for.

Two things `scout.mjs` learned the hard way and a new scanner should copy:

- **One unreadable directory costs that directory, not the scan.** A network mount that timed out mid-walk took down a whole run. Catch it per directory, carry on, and exit 3.
- **Rank the file that defines an imported name, not the file the import names.** A re-export barrel otherwise takes the score of everything behind it, and the file holding the actual definition ranks nowhere.

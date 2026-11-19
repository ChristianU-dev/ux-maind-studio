import { build } from "esbuild";
import { mkdir, readFile, writeFile, readdir, stat, cp, rm } from "node:fs/promises";
import { resolve, sep } from "node:path";

const outdir = "../ux_maind/app/web/generated";
await rm(outdir, { recursive: true, force: true });
await mkdir(outdir, { recursive: true });

const result = await build({
  entryPoints: ["components.js", "src/main.jsx"],
  entryNames: "[name]",
  outdir,
  bundle: true,
  format: "esm",
  splitting: true,
  minify: true,
  legalComments: "eof",
  target: "es2022",
  define: { "process.env.NODE_ENV": '"production"' },
  metafile: true,
});

await writeFile(
  outdir + "/build.json",
  JSON.stringify({ builder: "esbuild 0.25.11", ...result.metafile }, null, 2)
);

const bundled = new Set(["pdfjs-dist"]);
for (const inp of Object.keys(result.metafile.inputs || {})) {
  const norm = inp.replaceAll("\\", "/");
  if (norm.includes("node_modules/")) {
    const after = norm.split("node_modules/")[1];
    const parts = after.split("/");
    bundled.add(parts[0].startsWith("@") ? `${parts[0]}/${parts[1]}` : parts[0]);
  }
}

let notices =
  "Locally built 100% open-source browser components; zero proprietary dependencies; zero runtime CDNs.\n";
for (const p of [...bundled].sort()) {
  const root = "node_modules/" + p;
  const meta = JSON.parse(await readFile(root + "/package.json", "utf8"));
  const licFile = (await readdir(root)).find((n) => /^licen[cs]e(?:\.md|\.txt)?$/i.test(n));
  notices +=
    `\n${p} ${meta.version} (${meta.license})\n` +
    (licFile ? await readFile(root + "/" + licFile, "utf8") : "See package SPDX identifier above.") +
    "\n";
}
await writeFile(outdir + "/LICENSES.txt", notices);

const pdfOut = resolve(outdir, "pdfjs");
if (!pdfOut.startsWith(resolve(outdir) + sep)) throw Error("Unsafe generated path");
await mkdir(pdfOut, { recursive: true });
for (const part of [
  "build/pdf.mjs",
  "build/pdf.worker.mjs",
  "web/pdf_viewer.mjs",
  "web/pdf_viewer.css",
  "web/images",
  "cmaps",
  "standard_fonts",
  "wasm",
]) {
  await cp("node_modules/pdfjs-dist/" + part, outdir + "/pdfjs/" + part, { recursive: true });
}
await mkdir(outdir + "/docs", { recursive: true });
for (const docFile of ["USER_MANUAL.md", "SYSTEM_LIMITS.md"]) {
  try {
    await cp("../docs/" + docFile, outdir + "/docs/" + docFile);
  } catch {
    // Optional if built outside full repository checkout
  }
}
for (const f of await readdir(outdir)) {
  const st = await stat(outdir + "/" + f);
  console.log(f, st.isFile() ? st.size : 0);
}

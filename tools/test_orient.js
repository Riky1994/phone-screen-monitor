// 从 index.html 里抽出真实的 computeLayout() 做用例验证
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web", "index.html"), "utf8");

const m = html.match(/function computeLayout\(\) \{[\s\S]*?\n  \}/);
if (!m) {
  console.error("没能从 index.html 里找到 computeLayout()");
  process.exit(1);
}

let orientMode = "auto";
const window = { innerWidth: 0, innerHeight: 0 };
const computeLayout = eval("(" + m[0] + ")");

const cases = [
  // [mode, vw, vh, 期望 wide, 期望 rot]
  ["auto", 412, 915, false, 0],
  ["auto", 915, 412, true, 0],
  ["auto", 800, 800, false, 0],
  ["landscape", 412, 915, true, 90],
  ["landscape", 915, 412, true, 0],
  ["portrait", 915, 412, false, -90],
  ["portrait", 412, 915, false, 0],
  ["portrait", 1280, 800, false, -90],
];

let fail = 0;
for (const [mode, vw, vh, wantWide, wantRot] of cases) {
  orientMode = mode;
  window.innerWidth = vw;
  window.innerHeight = vh;
  const got = computeLayout();
  const ok = got.wide === wantWide && got.rot === wantRot;
  if (!ok) fail++;
  console.log(
    `${ok ? "OK  " : "FAIL"}  ${mode.padEnd(9)} ${vw}x${vh}  -> wide=${got.wide} rot=${got.rot}` +
      (ok ? "" : `   期望 wide=${wantWide} rot=${wantRot}`)
  );
}

console.log(fail === 0 ? "\n全部通过 ✓" : `\n${fail} 个用例失败`);
process.exit(fail === 0 ? 0 : 1);

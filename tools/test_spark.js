// 迷你走势路径生成的回归测试：node tools/test_spark.js
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const start = html.indexOf("function sparkPath(data, w, h) {");
const end = html.indexOf("function initSpark(", start);
if (start < 0 || end < 0) {
  console.error("FAIL: 没找到 sparkPath 定义");
  process.exit(1);
}
const sparkPath = new Function(html.slice(start, end) + "\nreturn sparkPath;")();

let bad = 0;
const ok = (name, cond, extra) => {
  if (cond) console.log("  ✓ " + name);
  else { console.log("  ✗ " + name + (extra ? "  → " + extra : "")); bad++; }
};

// 点数不足
ok("0 个点返回空串", sparkPath([], 100, 30) === "");
ok("1 个点返回空串", sparkPath([42], 100, 30) === "");

// 基本形状
const d2 = sparkPath([10, 50], 100, 30);
ok("两个点能生成路径", d2.startsWith("M") && d2.includes("L"), d2);
ok("坐标保留一位小数", /^M[\d.]+ [\d.]+L[\d.]+ [\d.]+$/.test(d2), d2);

// 值越大，y 越小（屏幕坐标向下为正）
const pair = (a, b) => sparkPath([a, b], 100, 30).match(/[\d.]+ ([\d.]+)/g).map(s => parseFloat(s.split(" ")[1]));
const [yLow, yHigh] = pair(10, 90);
ok("数值大的点画得更高", yHigh < yLow, `10%→${yLow}, 90%→${yHigh}`);

// 数值不超出画布
const flat = sparkPath([50, 50, 50], 100, 30);
ok("平线所有点同高", (flat.match(/L[\d.]+ ([\d.]+)/g) || []).every(s => s.split(" ")[1] === flat.match(/([\d.]+)$/)[1]));

// 自适应缩放：最大值顶到上沿，最小值贴近下沿
const ys = sparkPath([1, 100], 100, 30).match(/(?:M|L)[\d.]+ ([\d.]+)/g).map(s => parseFloat(s.split(" ")[1]));
ok("自适应缩放占满高度", Math.min(...ys) <= 4 && Math.max(...ys) >= 26, `y=${ys.join(",")}`);

// 路径点数 = 数据点数
const many = sparkPath([1, 2, 3, 4, 5, 6], 100, 30);
ok("6 个点生成 6 段指令", (many.match(/[ML]/g) || []).length === 6, many);

// 60 点窗口内不越界
const full = Array.from({ length: 60 }, (_, i) => i % 101);
const pts = full.length && sparkPath(full, 100, 30).match(/(?:M|L)([\d.]+) ([\d.]+)/g);
const xs = pts.map(p => parseFloat(p.slice(1).split(" ")[0]));
ok("满窗口横坐标不越界", xs.every(x => x >= -0.1 && x <= 100.1), `x范围 ${Math.min(...xs)}~${Math.max(...xs)}`);

console.log(bad ? `\n有 ${bad} 项失败` : "\n全部通过 ✓");
process.exitCode = bad ? 1 : 0;

// 告警红点逻辑回归测试：node tools/test_alerts.js
// 从 web/index.html 里抽出 updateAlerts，用桩对象跑几种场景。
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const start = html.indexOf("var alertState =");
const end = html.indexOf("function render(d) {", start);
if (start < 0 || end < 0) {
  console.error("FAIL: 没找到告警逻辑代码块");
  process.exit(1);
}
const code = html.slice(start, end);

// 可控时钟
let NOW = 1000000;
const realNow = Date.now;
Date.now = () => NOW;

const dot = {
  cls: new Set(),
  title: "",
  classList: {
    add(c) { dot.cls.add(c); },
    remove(c) { dot.cls.delete(c); },
  },
};
const hints = [];
const stub = ($, showHint, body) =>
  new Function("$", "showHint", body + "\nreturn { updateAlerts, alertState };")($, showHint);

const api = stub(() => dot, (t) => hints.push(t), code);
const { updateAlerts, alertState } = api;
const on = () => dot.cls.has("on");

const ok = (name, cond, extra) => {
  if (cond) console.log("  ✓ " + name);
  else {
    console.log("  ✗ " + name + (extra ? "  → " + extra : ""));
    process.exitCode = 1;
  }
};

const stats = (o) => Object.assign({
  cpu: { pct: 30 },
  gpu: { temp: 55 },
  disk: [{ mount: "C:", total: 200 * 1024 ** 3, used: 100 * 1024 ** 3 }],
}, o);

// 1. 一切正常 → 不显示
updateAlerts(stats({}));
ok("正常状态不亮红点", !on());

// 2. GPU 过热 → 立刻亮
updateAlerts(stats({ gpu: { temp: 90 } }));
ok("GPU 90°C 亮红点", on(), dot.title);
ok("提示里说明原因", /GPU/.test(dot.title), dot.title);

// 3. 磁盘剩余 <10GB
updateAlerts(stats({ disk: [{ mount: "D:", total: 100 * 1024 ** 3, used: 95 * 1024 ** 3 }] }));
ok("磁盘剩余 5GB 亮红点", on(), dot.title);
ok("提示包含盘符", /D:/.test(dot.title), dot.title);

// 4. CPU 90% 不够久 → 不亮
alertState.cpuSince = 0;
updateAlerts(stats({ cpu: { pct: 95 } }));
ok("CPU 刚超过 90% 不亮", !on());
NOW += 10000;
updateAlerts(stats({ cpu: { pct: 95 } }));
ok("持续 10 秒还不亮", !on());

// 5. 持续 30 秒以上 → 亮
NOW += 21000;
updateAlerts(stats({ cpu: { pct: 95 } }));
ok("持续 31 秒亮红点", on(), dot.title);

// 6. 回落 → 熄灭
updateAlerts(stats({ cpu: { pct: 40 } }));
ok("CPU 回落后熄灭", !on());
ok("计时器已重置", alertState.cpuSince === 0);

// 7. 同时满足多条 → 提示里都要有（CPU 需要重新累计 30 秒）
const triple = stats({
  cpu: { pct: 95 },
  gpu: { temp: 88 },
  disk: [{ mount: "C:", total: 100 * 1024 ** 3, used: 98 * 1024 ** 3 }],
});
NOW += 1000;
updateAlerts(triple);            // 开始计时
NOW += 31000;
updateAlerts(triple);            // 持续满 30 秒
ok("多条件同时触发", on() && /CPU/.test(dot.title) && /GPU/.test(dot.title) && /C:/.test(dot.title), dot.title);

Date.now = realNow;
console.log(process.exitCode ? "\n有失败项" : "\n全部通过 ✓");

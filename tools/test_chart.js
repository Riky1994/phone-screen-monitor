// 回归测试：横屏旋转下，趋势图位图尺寸不能被 getBoundingClientRect() 的对调宽高带偏
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web", "index.html"), "utf8");

function grab(name) {
  const re = new RegExp("function " + name + "\\(\\) \\{[\\s\\S]*?\\n  \\}");
  const m = html.match(re);
  if (!m) throw new Error("没能抽取到 " + name + "()");
  return m[0];
}

const src = grab("canvasBox") + "\n" + grab("fitCanvas");

global.window = { devicePixelRatio: 3 };

const factory = new Function(
  "cv",
  "ctx",
  '"use strict";\nvar CW = 0, CHh = 0;\n' +
    src +
    "\nreturn { fit: function(){ return fitCanvas(); }, size: function(){ return { w: CW, h: CHh, bw: cv.width, bh: cv.height, scale: ctx.scale }; } };\n"
);

function makeCanvas(layoutW, layoutH) {
  return {
    clientWidth: layoutW,
    clientHeight: layoutH,
    offsetWidth: layoutW,
    offsetHeight: layoutH,
    width: 0,
    height: 0,
    // 模拟"祖先被 rotate(90deg)"：外接矩形宽高对调（这正是原 bug 的来源）
    getBoundingClientRect() {
      return { width: this.clientHeight, height: this.clientWidth };
    }
  };
}

const ctx = { scale: 0, setTransform(s) { this.scale = s; } };
let fail = 0;

function check(name, got, want) {
  const ok = got === want;
  if (!ok) fail++;
  console.log(`${ok ? "OK  " : "FAIL"}  ${name}: ${got}${ok ? "" : "  期望 " + want}`);
}

// 1) 横屏旋转后的画布：布局 891x84，外接矩形是 84x891
const cv = makeCanvas(891, 84);
const api = factory(cv, ctx);
api.fit();
let s = api.size();
check("横屏 CW（逻辑宽）", s.w, 891);
check("横屏 CHh（逻辑高）", s.h, 84);
check("横屏位图宽", s.bw, 891 * 3);
check("横屏位图高", s.bh, 84 * 3);
check("横屏 DPR 变换", s.scale, 3);

// 2) 同样尺寸重复调用不应重分配（重分配会清屏）
check("重复调用返回 false", api.fit(), false);

// 3) 竖屏尺寸变化后应重新分配
const cv2 = makeCanvas(388, 98);
const api2 = factory(cv2, ctx);
api2.fit();
let s2 = api2.size();
check("竖屏 CW", s2.w, 388);
check("竖屏 CHh", s2.h, 98);
check("竖屏位图宽", s2.bw, 388 * 3);

// 4) 切换横竖屏（同一元素尺寸变化）后要重新分配
check("换尺寸后 fit 返回 true", (function () {
  cv.clientWidth = 388;
  cv.clientHeight = 98;
  return api.fit();
})(), true);
check("换尺寸后 CW", api.size().w, 388);

console.log(fail === 0 ? "\n全部通过 ✓" : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);

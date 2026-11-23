// 符号弹窗：桌面端悬停 / 键盘聚焦显示；手机上点一下打开、点别处关闭。
// 同时保证弹窗不会超出屏幕左右边缘，靠近顶部时改为向下弹出。
(function () {
  function place(sym) {
    const pop = sym.querySelector(".pop");
    if (!pop) return;
    pop.style.setProperty("--dx", "0px");
    sym.classList.remove("below");
    const r = pop.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    let dx = 0;
    if (r.left < 8) dx = 8 - r.left;
    if (r.right > vw - 8) dx = vw - 8 - r.right;
    pop.style.setProperty("--dx", dx + "px");
    if (r.top < 70) sym.classList.add("below");
  }
  document.querySelectorAll("[data-sym]").forEach(function (sym) {
    sym.addEventListener("pointerenter", function () { place(sym); });
    sym.addEventListener("focus", function () { place(sym); });
    sym.addEventListener("click", function (e) {
      e.stopPropagation();
      const open = sym.classList.contains("open");
      document.querySelectorAll(".sym.open").forEach(function (s) { s.classList.remove("open"); });
      if (!open) { sym.classList.add("open"); place(sym); }
    });
  });
  document.addEventListener("click", function () {
    document.querySelectorAll(".sym.open").forEach(function (s) { s.classList.remove("open"); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") document.querySelectorAll(".sym.open").forEach(function (s) { s.classList.remove("open"); });
  });
})();

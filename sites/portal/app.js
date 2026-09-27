/* Portal step logic. No storage of any kind: values live in the DOM only, and
   Submit navigates to receipt.html, which makes up a receipt number on load. */
(function () {
  "use strict";
  var form = document.getElementById("application");
  var steps = Array.prototype.slice.call(document.querySelectorAll(".step"));
  var progress = document.querySelectorAll("#progress li");
  var current = 1;

  function show(step) {
    current = step;
    steps.forEach(function (s) { s.hidden = Number(s.dataset.step) !== step; });
    progress.forEach(function (li) {
      var n = Number(li.dataset.step);
      li.classList.toggle("active", n === step);
      li.classList.toggle("done", n < step);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
    var heading = document.querySelector("#step-" + step + " h2");
    if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus(); }
  }

  function money(n) { return "$" + (Number(n) || 0).toLocaleString("en-US"); }

  function lossTotal() {
    var total = 0;
    document.querySelectorAll('input[id^="loss-cost-"]').forEach(function (i) { total += Number(i.value) || 0; });
    return total;
  }
  function lossCount() {
    var count = 0;
    document.querySelectorAll('input[id^="loss-item-"]').forEach(function (i) { if (i.value.trim()) count++; });
    return count;
  }
  function refreshTotal() { document.getElementById("loss-total").textContent = money(lossTotal()); }

  // Step navigation buttons (the two "Back" ids per direction are unique on the page).
  var nav = {
    "to-step-2": 2, "to-step-3": 3, "to-step-4": 4,
    "to-step-1": 1, "to-step-2b": 2, "to-step-3b": 3
  };
  Object.keys(nav).forEach(function (id) {
    var btn = document.getElementById(id);
    if (btn) btn.addEventListener("click", function () {
      if (nav[id] === 4) fillReview();
      show(nav[id]);
    });
  });

  // Losses: live total + add another row.
  document.getElementById("loss-rows").addEventListener("input", refreshTotal);
  var addBtn = document.getElementById("add-loss");
  var rowCount = 3;
  addBtn.addEventListener("click", function () {
    rowCount += 1;
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td><input type="text" id="loss-item-' + rowCount + '" name="loss_item_' + rowCount + '" aria-label="Loss item ' + rowCount + '"></td>' +
      '<td class="cost"><input type="number" id="loss-cost-' + rowCount + '" name="loss_cost_' + rowCount + '" min="0" step="1" aria-label="Loss cost ' + rowCount + '"></td>';
    document.getElementById("loss-rows").appendChild(tr);
  });

  function textOrDash(v) { return v && String(v).trim() ? v : "—"; }

  function fillReview() {
    var damageSel = document.getElementById("damage-type");
    var damageLabel = damageSel.value ? damageSel.options[damageSel.selectedIndex].text : "—";
    var water = document.getElementById("water-height").value;
    var files = document.getElementById("evidence-upload").files;
    var fileNames = [];
    for (var i = 0; i < files.length; i++) fileNames.push(files[i].name);

    document.getElementById("review-name").textContent = textOrDash(document.getElementById("applicant-name").value);
    document.getElementById("review-phone").textContent = textOrDash(document.getElementById("applicant-phone").value);
    document.getElementById("review-address").textContent = textOrDash(document.getElementById("applicant-address").value);
    document.getElementById("review-damage").textContent = damageLabel;
    document.getElementById("review-water").textContent = water ? water + " inches" : "—";
    document.getElementById("review-evidence").textContent = fileNames.length ? fileNames.join(", ") : "None uploaded";
    document.getElementById("review-items").textContent = lossCount() + " item" + (lossCount() === 1 ? "" : "s");
    document.getElementById("review-total").textContent = money(lossTotal());
  }

  // Submit: no data leaves the page; go to the receipt.
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    window.location.href = "receipt.html";
  });

  // Optional deep link (?step=2) so the agent / vision check can land on a known step.
  var wanted = Number(new URLSearchParams(location.search).get("step"));
  show(wanted >= 1 && wanted <= 4 ? wanted : 1);
  if (wanted === 4) fillReview();
})();

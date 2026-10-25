/* heatmap.js - makes the CNN attention image (Grad-CAM) big, and enlarges it when you tap it.
 * The page puts that image in the same row as the two photo boxes, so it came out tiny. This moves it below that row,
 * makes it full width, and opens it full screen on tap. It only changes how the image looks, nothing else.
 */
(function () {
  'use strict';

  function enlarge(src) {
    var o = document.createElement('div');
    o.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:100000;background:rgba(5,15,35,.93);display:flex;align-items:center;justify-content:center;padding:16px;cursor:zoom-out';
    var i = document.createElement('img');
    i.src = src;
    i.alt = 'CNN attention map (enlarged)';
    i.style.cssText = 'max-width:100%;max-height:100%;border-radius:10px';
    o.appendChild(i);
    o.addEventListener('click', function () { if (o.parentNode) o.parentNode.removeChild(o); });
    document.body.appendChild(o);
  }

  var busy = false;
  function tidy() {
    if (busy) return;
    busy = true;
    try {
      var boxes = document.querySelectorAll('[id^="cam-"]');
      for (var k = 0; k < boxes.length; k++) {
        var el = boxes[k], row = el.parentElement;
        if (row && row.style && row.style.display === 'flex' && row.parentElement) {      // it sits beside the photo boxes: move it below them
          row.parentElement.insertBefore(el, row.nextSibling);
        }
        el.style.width = '100%';
        el.style.boxSizing = 'border-box';
        el.style.marginBottom = '10px';
        el.style.cursor = 'zoom-in';
        var cap = el.firstElementChild;
        if (cap && cap.textContent.indexOf('tap to enlarge') === -1) cap.appendChild(document.createTextNode(' (tap to enlarge)'));
      }
    } finally { busy = false; }
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (t && t.tagName === 'IMG' && t.closest && t.closest('[id^="cam-"]')) enlarge(t.src);
  });

  if (window.MutationObserver) new MutationObserver(tidy).observe(document.body, { childList: true, subtree: true });
  tidy();
})();

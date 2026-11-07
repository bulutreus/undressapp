(function () {
  "use strict";

  var videos = document.querySelectorAll("video[data-lazy-autoplay]");
  if (!videos.length) return;
  var previewRequested = new WeakSet();

  function showPreviewFrame(video) {
    video.preload = "metadata";
    if (previewRequested.has(video) || video.readyState >= 2) return;
    previewRequested.add(video);

    video.addEventListener(
      "loadedmetadata",
      function () {
        if (!Number.isFinite(video.duration) || video.duration <= 0) return;
        video.addEventListener("seeked", function () { video.pause(); }, { once: true });
        try {
          video.currentTime = Math.min(0.1, video.duration / 2);
        } catch (error) {
          console.warn("Unable to seek to the preset preview frame:", video.currentSrc, error);
        }
      },
      { once: true }
    );
    video.load();
  }

  function startPlayback(video) {
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    var playback = video.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(function (error) {
        console.warn("Preset video autoplay was blocked:", video.currentSrc, error);
        showPreviewFrame(video);
      });
    }
  }

  videos.forEach(function (video) {
    video.addEventListener(
      "error",
      function () {
        console.error("Preset video failed to load:", video.currentSrc, video.error);
        showPreviewFrame(video);
      },
      { once: true }
    );
  });

  window.addEventListener("message", function (event) {
    if (!event.data || event.data.type !== "miniapp-route-leaving") return;
    videos.forEach(function (video) {
      video.pause();
      video.preload = "none";
      video.load();
    });
  });

  // Wait until the page has rendered before starting all previews together;
  // this keeps video requests from delaying the Video menu transition.
  function startAllPreviews() {
    videos.forEach(startPlayback);
  }

  if (document.readyState === "complete") {
    window.setTimeout(startAllPreviews, 0);
  } else {
    window.addEventListener("load", startAllPreviews, { once: true });
  }
})();

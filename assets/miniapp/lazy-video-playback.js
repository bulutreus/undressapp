(function () {
  "use strict";

  var videos = document.querySelectorAll("video[data-lazy-autoplay]");
  if (!videos.length) return;
  var previewRequested = new WeakSet();
  var isMobile = window.matchMedia("(max-width: 640px)").matches;

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
    var playback = video.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(function (error) {
        console.warn("Preset video autoplay was blocked:", video.currentSrc, error);
        showPreviewFrame(video);
      });
    }
  }

  if (isMobile) {
    videos.forEach(function (video) {
      var source = video.querySelector("source[data-mobile-src]");
      var mobileSource = source && source.getAttribute("data-mobile-src");
      if (!mobileSource) return;
      source.setAttribute("src", mobileSource);
      video.load();
    });
  }

  if (!("IntersectionObserver" in window)) {
    videos.forEach(startPlayback);
    return;
  }

  var visibility = new Map();

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

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        visibility.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      });

      if (isMobile) {
        // On phones, concurrent previews compete for bandwidth and delay the
        // video the user is currently looking at. Play only the most visible.
        var activeVideo = null;
        var activeRatio = 0;
        visibility.forEach(function (ratio, video) {
          if (ratio > activeRatio) {
            activeVideo = video;
            activeRatio = ratio;
          }
          if (ratio === 0) video.pause();
        });
        visibility.forEach(function (_ratio, video) {
          if (video !== activeVideo) video.pause();
        });
        if (activeVideo) startPlayback(activeVideo);
        return;
      }

      entries.forEach(function (entry) {
        if (entry.isIntersecting) startPlayback(entry.target);
        else entry.target.pause();
      });
    },
    { rootMargin: isMobile ? "48px 0px" : "160px 0px", threshold: [0.1, 0.25, 0.5, 0.75] }
  );

  videos.forEach(function (video) {
    observer.observe(video);
  });
})();

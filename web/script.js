//캐시 변수
const summaryCache = new Map();

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0, n = bytes;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${u[i]}`;
}

function formatTime(secs) {
  if (!Number.isFinite(secs)) return "길이 계산 중…";
  const s = Math.floor(secs % 60).toString().padStart(2, "0");
  const m = Math.floor((secs / 60) % 60).toString().padStart(2, "0");
  const h = Math.floor(secs / 3600);
  return h ? `${h}:${m}:${s}` : `${m}:${s}`;
}

const els = {
  loadBtn: document.getElementById("loadBtn"),
  folderBtn: document.getElementById("folderBtn"),
  fileInput: document.getElementById("fileInput"),
  folderInput: document.getElementById("folderInput"),
  useMultipassToggle: document.getElementById("useMultipassToggle"),
  videoList: document.getElementById("videoList"),
  videoCount: document.getElementById("videoCount"),
};

const state = {
  items: [],
  selectedId: null,
  batchQueue: [],
  batchRunning: false,
  useMultipass: true,
};

els.loadBtn.addEventListener("click", () => els.fileInput.click());

if (els.useMultipassToggle) {
  state.useMultipass = !!els.useMultipassToggle.checked;
  els.useMultipassToggle.addEventListener("change", () => {
    state.useMultipass = !!els.useMultipassToggle.checked;
  });
}

function addFiles(files) {
  const list = Array.from(files || []);
  if (!list.length) return;
  const videos = list.filter(f => {
    const byType = typeof f.type === "string" && f.type.startsWith("video/");
    const byExt = /\.(mp4|mov|avi|webm)$/i.test(f.name || "");
    return byType || byExt;
  });
  if (!videos.length) return;

  const existingKey = new Set(state.items.map(i => `${i.file.name}-${i.file.size}`));

  for (const file of videos) {
    const key = `${file.name}-${file.size}`;
    if (existingKey.has(key)) continue;

    const url = URL.createObjectURL(file);
    const id = crypto.randomUUID();
    const item = { id, file, url, duration: undefined };
    state.items.push(item);
    renderItem(item);
    probeDuration(item);

    // enqueue for background batch analysis
    state.batchQueue.push(file);
  }

  updateCount();

  // kick off batch processing if not already running
  if (!state.batchRunning) {
    runBatchAnalysis();
  }
}

els.fileInput.addEventListener("change", (e) => {
  const files = e.target.files;
  addFiles(files);
  els.fileInput.value = "";
});

els.folderBtn.addEventListener("click", () => els.folderInput.click());

els.folderInput.addEventListener("change", (e) => {
  const files = e.target.files;
  addFiles(files);
  els.folderInput.value = "";
});

function probeDuration(item) {
  const v = document.createElement("video");
  v.preload = "metadata";
  v.muted = true;
  v.src = item.url;

  v.addEventListener("loadedmetadata", () => {
    item.duration = v.duration;
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatTime(item.duration)} • ${formatBytes(item.file.size)}`;
    }
    v.removeAttribute("src");
    v.load();
  }, { once: true });

  v.addEventListener("error", () => {
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatBytes(item.file.size)}`;
    }
  }, { once: true });
}

function renderItem(item) {
  const li = document.createElement("li");
  li.className = "video-item";
  li.dataset.id = item.id;

  const thumb = document.createElement("div");
  thumb.className = "video-thumb";

  //썸네일 이미지 element 준비
  const img = document.createElement("img");
  img.style.display = "none"; // 로딩 전까지 숨김
  thumb.appendChild(img);

  const meta = document.createElement("div");
  meta.className = "video-meta";

  const name = document.createElement("div");
  name.className = "video-name";
  name.title = item.file.name;
  name.textContent = item.file.name;

  const info = document.createElement("div");
  info.className = "video-info";
  info.textContent = `${formatBytes(item.file.size)}`;

  meta.append(name, info);

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = item.file.type.replace("video/", "") || "video";

  //삭제 버튼
  const delBtn = document.createElement("button");
  delBtn.className = "delete-btn";
  delBtn.innerHTML = "🗑️";

  delBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    state.items = state.items.filter(v => v.id !== item.id);
    li.remove();
    updateCount();
  });

  li.append(thumb, meta, badge, delBtn);
  els.videoList.appendChild(li);

  //항목 클릭하면 재생 및 분석
  li.addEventListener("click", () => {
    state.selectedId = item.id;
    player.src = item.url;
    player.style.display = "block";
    player.play();

    //영상 제목 표시
    document.getElementById("videoTitle").textContent = item.file.name;

    //설명칸 초기화(요약 가져오기)
    document.getElementById("videoDesc").textContent = "";

    // 이미 캐시에 있으면 화면만 갱신 (분석 트리거 X)
    showCachedResultIfAvailable(item.file);
  });


  //썸네일 불러오기
  generateThumbnail(item.file, item.url, (dataURL) => {
    img.src = dataURL;
    img.style.display = "block";
  });
}

//캐시 생성
function buildCacheKey(file) {
  return [
    file.name,
    file.size,
    file.lastModified
  ].join("|");
}

/*영상 전송 및 분석*/
async function analyzeVideo(file, silent = false) {
  const filename = file.name;
  const cacheKey = buildCacheKey(file);

  const descEl = document.getElementById("videoDesc");
  if (!silent) {
    descEl.textContent = "🔍 분석 중…";
  }

  //프론트 캐시 먼저 확인
  if (summaryCache.has(cacheKey)) {
    const data = summaryCache.get(cacheKey);
    if (!silent || isCurrentlySelected(filename)) {
      descEl.textContent = data.content_summary || "(설명 없음)";
      fillResultTable(data);
    }
    return;
  }

  //서버 캐시 확인
  let cached = await fetch(`http://127.0.0.1:5001/api/results/${encodeURIComponent(filename)}`);
  if (cached.ok) {
    const data = await cached.json();
    summaryCache.set(cacheKey, data);
    if (!silent || isCurrentlySelected(filename)) {
      descEl.textContent = data.content_summary || "(설명 없음)";
      fillResultTable(data);
    }
    return; 
  }

  //서버에 새로운 분석 요청
  const form = new FormData();
  form.append("video", file, filename);

  const endpoint = state.useMultipass
    ? "http://127.0.0.1:5001/api/analyze/multipass?filename=" + encodeURIComponent(filename)
    : "http://127.0.0.1:5001/api/analyze/summary?filename=" + encodeURIComponent(filename);

  const res = await fetch(endpoint, {
    method: "POST",
    body: form
  });

  const data = await res.json();

  // When using single-pass summary endpoint, persist the result as well
  if (!state.useMultipass) {
    try {
      await fetch(`http://127.0.0.1:5001/api/results/${encodeURIComponent(filename)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
    } catch (_) {
      // non-fatal
    }
  }

  //프론트 캐시에 저장
  summaryCache.set(cacheKey, data);

  if (!silent || isCurrentlySelected(filename)) {
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);
  }
}

function isCurrentlySelected(filename) {
  return (document.getElementById("videoTitle").textContent || "") === filename;
}

async function showCachedResultIfAvailable(file) {
  const filename = file.name;
  const cacheKey = buildCacheKey(file);
  const descEl = document.getElementById("videoDesc");

  if (summaryCache.has(cacheKey)) {
    const data = summaryCache.get(cacheKey);
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);
    return;
  }

  // 서버 저장본만 조회 (분석 트리거 X)
  try {
    const resp = await fetch(`http://127.0.0.1:5001/api/results/${encodeURIComponent(filename)}`);
    if (resp.ok) {
      const data = await resp.json();
      summaryCache.set(cacheKey, data);
      descEl.textContent = data.content_summary || "(설명 없음)";
      fillResultTable(data);
    }
  } catch (_) {
    // ignore
  }
}

async function runBatchAnalysis() {
  if (state.batchRunning) return;
  state.batchRunning = true;
  try {
    while (state.batchQueue.length > 0) {
      const file = state.batchQueue.shift();
      try {
        await analyzeVideo(file, true); // silent batch
      } catch (_) {
        // continue to next
      }
      // brief delay to avoid overloading the server
      await new Promise(r => setTimeout(r, 300));
    }
  } finally {
    state.batchRunning = false;
  }
}


function fillResultTable(data) {
  const scoreKeys = [
    "topic", 
    "sexuality", 
    "violence", 
    "horror", 
    "drugs", 
    "language", 
    "imitable"
  ];

  const table = document.getElementById("resultTable");
  const rows = table.querySelectorAll("tbody tr");

  scoreKeys.forEach((key, index) => {
    const row = rows[index]; // 0~6행

    //점수는 2열
    const scoreCell = row.children[1];
    scoreCell.textContent = data.scores[key] ?? "";

    //근거(details)는 3열
    const detailCell = row.children[2];
    detailCell.textContent = data.details[key] ?? "";
  });
}


function updateCount() {
  els.videoCount.textContent = `${state.items.length}개`;
}

window.addEventListener("beforeunload", () => {
  state.items.forEach(i => URL.revokeObjectURL(i.url));
});


//1초 기준으로 썸네일 생성
function generateThumbnail(file, url, callback) {
  const video = document.createElement("video");
  video.src = url;
  video.muted = true;
  video.preload = "auto";

  video.addEventListener("loadedmetadata", () => {
    const targetTime = video.duration > 1 ? 1 : 0.1;
    video.currentTime = targetTime;
  });

  video.addEventListener("seeked", () => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 90;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataURL = canvas.toDataURL("image/jpeg", 0.8);
    callback(dataURL);
  }, { once: true });
}

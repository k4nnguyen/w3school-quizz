let sourceQuizzes = [];
let availableTopics = new Set();
let currentQuiz = [];
let correctCount = 0;
let answeredCount = 0;

document.addEventListener("DOMContentLoaded", () => {
  loadData();

  document.getElementById("btn-start-quiz").addEventListener("click", (ev) => {
    ev.preventDefault();
    startQuiz();
  });

  document.getElementById("btn-select-all").addEventListener("click", (ev) => {
    ev.preventDefault();
    selectAll(true);
  });

  document.getElementById("btn-deselect-all").addEventListener("click", (ev) => {
    ev.preventDefault();
    selectAll(false);
  });

  document.getElementById("btn-restart").addEventListener("click", (ev) => {
    ev.preventDefault();
    location.reload();
  });

  document.getElementById("btn-review-again").addEventListener("click", (ev) => {
    ev.preventDefault();
    location.reload();
  });
});

async function loadData() {
  try {
    const response = await fetch("quizzes.json");
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    sourceQuizzes = await response.json();

    sourceQuizzes.forEach((q) => {
      if (q.topic) {
        availableTopics.add(q.topic);
      }
    });

    renderTopicsSelection(Array.from(availableTopics).sort());
    document.getElementById("btn-start-quiz").removeAttribute("disabled");
  } catch (err) {
    console.error(err);
    document.getElementById("topics-container").innerHTML = `
            <div class="col-12 text-center text-danger border p-3 rounded bg-white">
                <h6>Không thể tải dữ liệu câu hỏi (quizzes.json)</h6>
                <p class="mb-0 small">Bật Web Server (vd: Live Server / Python HTTP Server) do trình duyệt chặn đọc file JSON cục bộ (CORS error).</p>
            </div>
        `;
  }
}

function renderTopicsSelection(topics) {
  const container = document.getElementById("topics-container");
  container.innerHTML = "";

  topics.forEach((topic, idx) => {
    const id = `topic-${idx}`;
    const div = document.createElement("div");
    div.className = "col-6 col-md-4 col-lg-3";
    div.innerHTML = `
            <input type="checkbox" id="${id}" class="topic-checkbox" value="${topic}" checked>
            <label class="topic-checkbox-label w-100 h-100 d-flex align-items-center justify-content-center" for="${id}">
                ${topic.toUpperCase()}
            </label>
        `;
    container.appendChild(div);
  });
}

function selectAll(check) {
  const boxes = document.querySelectorAll(".topic-checkbox");
  boxes.forEach((box) => (box.checked = check));
}

// Hàm xáo trộn mảng thuật toán Fisher-Yates
function shuffleArray(array) {
  const newArr = [...array];
  for (let i = newArr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [newArr[i], newArr[j]] = [newArr[j], newArr[i]];
  }
  return newArr;
}

function startQuiz() {
  // Thu thập các topic đang chọn
  const checkedBoxes = Array.from(document.querySelectorAll(".topic-checkbox:checked")).map((b) => b.value);

  if (checkedBoxes.length === 0) {
    alert("Vui lòng chọn ít nhất một chủ đề để ôn tập!");
    return;
  }

  let limit = parseInt(document.getElementById("question-limit").value, 10);
  if (isNaN(limit) || limit < 0) limit = 0;

  // Lọc data theo topic
  const filtered = sourceQuizzes.filter((q) => checkedBoxes.includes(q.topic));

  // Shuffle câu hỏi
  currentQuiz = shuffleArray(filtered);
  if (limit > 0 && limit < currentQuiz.length) {
    currentQuiz = currentQuiz.slice(0, limit);
  }

  correctCount = 0;
  answeredCount = 0;

  document.getElementById("setup-section").classList.add("d-none");
  document.getElementById("quiz-title").innerText = `Ôn tập: ${currentQuiz.length} câu (Chủ đề: ${checkedBoxes.join(", ")})`;

  renderQuestions(currentQuiz);

  document.getElementById("quiz-section").classList.remove("d-none");
}

function renderQuestions(questions) {
  const container = document.getElementById("questions-container");
  container.innerHTML = "";

  questions.forEach((q, idx) => {
    // Shuffle mảng options
    const shuffledOptions = shuffleArray(q.options);

    // Tạo layout card câu hỏi
    const card = document.createElement("div");
    card.className = "card shadow-sm mb-4 border-0";

    let html = `
            <div class="card-body p-4">
                <div class="d-flex mb-3">
                    <span class="badge bg-primary me-2 align-self-start">Câu ${idx + 1}</span>
                    <span class="badge bg-secondary me-2 align-self-start">${(q.topic || "").toUpperCase()}</span>
                </div>
                <h5 class="card-title fw-bold mb-4">${escapeHtml(q.question)}</h5>
                <div class="options-group" id="q-options-${idx}">
        `;

    shuffledOptions.forEach((opt, optIndex) => {
      html += `
                <button 
                    class="btn btn-light option-btn fw-normal" 
                    data-qidx="${idx}" 
                    data-answer="${escapeHtml(opt)}"
                    onclick="handleAnswer(this)"
                >
                    ${escapeHtml(opt)}
                </button>
            `;
    });

    html += `
                </div>
                <div id="explanation-${idx}" class="mt-3 p-3 explanation-alert d-none rounded">
                    <strong>Giải thích:</strong> <span class="content">${q.explanation ? escapeHtml(q.explanation) : "Không có giải thích chi tiết."}</span>
                </div>
            </div>
        `;

    card.innerHTML = html;
    container.appendChild(card);
  });

  document.getElementById("finish-area").classList.add("d-none");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// Hàm toàn cục gọi bởi attribute onclick html inline
window.handleAnswer = function (button) {
  const qIndex = parseInt(button.getAttribute("data-qidx"));
  const selectedAnswerTxt = button.getAttribute("data-answer");
  const container = document.getElementById(`q-options-${qIndex}`);
  const qData = currentQuiz[qIndex];
  let correctStr = qData.correct;

  // Vô hiệu hoá tất cả nt trong group options
  const allButtons = container.querySelectorAll(".option-btn");
  allButtons.forEach((b) => {
    b.disabled = true;
    // Kiểm tra xem đâu là button chứa đáp án đúng để tô xanh trước
    if (b.getAttribute("data-answer") === correctStr) {
      b.classList.add("show-correct");
    }
  });

  // Check đúng sai cho button click -> đè css
  if (selectedAnswerTxt === correctStr) {
    button.classList.add("selected-correct");
    correctCount++;
  } else {
    button.classList.add("selected-wrong");
  }

  // Hiển thị giải thích
  const expDiv = document.getElementById(`explanation-${qIndex}`);
  if (expDiv) expDiv.classList.remove("d-none");

  answeredCount++;
  if (answeredCount === currentQuiz.length) {
    document.getElementById("finish-area").classList.remove("d-none");
    let percentage = Math.round((correctCount / currentQuiz.length) * 100);
    document.getElementById("score-text").innerText = `Bạn đã đạt ${correctCount}/${currentQuiz.length} điểm (${percentage}%)`;
  }
};

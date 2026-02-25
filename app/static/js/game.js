const pin = window.QUIZBATTLE_PIN;
const playerRaw = localStorage.getItem('qb_player');
if (!playerRaw) {
  window.location.href = '/';
}
const player = playerRaw ? JSON.parse(playerRaw) : null;
if (!player || player.pin !== pin) {
  window.location.href = '/';
}

const topicEl = document.getElementById('topic');
const scoreA = document.getElementById('score-a');
const scoreB = document.getElementById('score-b');
const turnEl = document.getElementById('turn');
const teamAList = document.getElementById('team-a-list');
const teamBList = document.getElementById('team-b-list');
const qTitle = document.getElementById('question-title');
const qText = document.getElementById('question-text');
const answersEl = document.getElementById('answers');
const resultEl = document.getElementById('answer-result');
const startBtn = document.getElementById('start-btn');
const timerEl = document.getElementById('timer');

let ws;
let currentQuestionId = null;
let localTimer = null;
let leftSeconds = 30;

function wsUrl(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${path}`;
}

function startCountdown() {
  clearInterval(localTimer);
  leftSeconds = 30;
  timerEl.textContent = `Осталось: ${leftSeconds} сек`;
  localTimer = setInterval(() => {
    leftSeconds -= 1;
    timerEl.textContent = leftSeconds > 0 ? `Осталось: ${leftSeconds} сек` : 'Время вышло';
    if (leftSeconds <= 0) clearInterval(localTimer);
  }, 1000);
}

function renderTeams(players) {
  teamAList.innerHTML = '';
  teamBList.innerHTML = '';
  players.forEach((p) => {
    const li = document.createElement('li');
    li.textContent = `${p.name}${p.is_host ? ' (host)' : ''}`;
    if (p.team === 'A') {
      li.className = 'team-a';
      teamAList.appendChild(li);
    } else {
      li.className = 'team-b';
      teamBList.appendChild(li);
    }
  });
}

function renderAnswers(options, enabled) {
  answersEl.innerHTML = '';
  options.forEach((option, idx) => {
    const btn = document.createElement('button');
    btn.className = 'secondary';
    btn.textContent = `${idx + 1}) ${option}`;
    btn.disabled = !enabled;
    btn.addEventListener('click', () => {
      btn.disabled = true;
      Array.from(answersEl.querySelectorAll('button')).forEach((b) => (b.disabled = true));
      ws.send(JSON.stringify({action: 'answer', option_index: idx + 1}));
    });
    answersEl.appendChild(btn);
  });
}

function renderState(state) {
  topicEl.textContent = `Тема: ${state.topic}`;
  scoreA.textContent = state.score_a;
  scoreB.textContent = state.score_b;
  renderTeams(state.players);

  if (state.status === 'waiting') {
    turnEl.textContent = 'Лобби: ждём игроков';
    qTitle.textContent = 'Вопрос';
    qText.textContent = `PIN комнаты: ${state.pin}`;
    answersEl.innerHTML = '';
    timerEl.textContent = '';
    if (state.players.find((p) => p.id === player.player_id && p.is_host)) {
      startBtn.classList.remove('hidden');
    }
  } else if (state.status === 'in_progress') {
    startBtn.classList.add('hidden');
    turnEl.textContent = state.current_team === 'A' ? 'Сейчас отвечает команда A' : 'Сейчас отвечает команда B';
    if (state.current_question) {
      qTitle.textContent = `Раунд ${state.current_question.order_index + 1}`;
      qText.textContent = state.current_question.text;
      const me = state.players.find((p) => p.id === player.player_id);
      const canAnswer = me && me.team === state.current_team && currentQuestionId !== state.current_question.id;
      renderAnswers(state.current_question.options, canAnswer);
      if (currentQuestionId !== state.current_question.id) {
        currentQuestionId = state.current_question.id;
        resultEl.textContent = '';
        startCountdown();
      }
    }
  } else {
    turnEl.textContent = 'Игра завершена';
    clearInterval(localTimer);
    timerEl.textContent = '';
    answersEl.innerHTML = '';
    if (state.winner === 'draw') {
      qText.textContent = 'Ничья! Отличная игра.';
    } else {
      qText.textContent = `Победила команда ${state.winner}!`;
    }
  }
}

startBtn.addEventListener('click', async () => {
  startBtn.disabled = true;
  try {
    const res = await fetch(`/games/${pin}/start`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({host_player_id: player.player_id}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось стартовать');
  } catch (err) {
    resultEl.textContent = err.message;
    startBtn.disabled = false;
  }
});

function connect() {
  ws = new WebSocket(wsUrl(`/ws/${pin}/${player.player_id}`));

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state') {
      renderState(msg.data);
    }
    if (msg.type === 'answer_result') {
      if (msg.data.timeout) {
        resultEl.textContent = 'Время вышло. Вопрос проигран.';
      } else {
        resultEl.textContent = msg.data.correct ? 'Верно! +1 балл' : `Неверно. Правильный ответ: ${msg.data.correct_option}`;
      }
    }
  };

  ws.onclose = () => {
    setTimeout(connect, 2000);
  };
}

connect();

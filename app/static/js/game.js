const pin = window.QUIZBATTLE_PIN;
const playerRaw = localStorage.getItem('qb_player');
if (!playerRaw) window.location.href = '/';
const player = playerRaw ? JSON.parse(playerRaw) : null;
if (!player || player.pin !== pin) window.location.href = '/';

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
const timerEl = document.getElementById('timer');
const voteStatsEl = document.getElementById('vote-stats');
const startBtn = document.getElementById('start-btn');
const saveResultsBtn = document.getElementById('save-results-btn');

let ws;
let currentQuestionId = null;
let localTimer = null;
let leftSeconds = 30;
let latestState = null;

function wsUrl(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${path}`;
}

function startCountdown(seconds) {
  clearInterval(localTimer);
  leftSeconds = seconds;
  timerEl.textContent = `До старта: ${leftSeconds}`;
  localTimer = setInterval(() => {
    leftSeconds -= 1;
    timerEl.textContent = leftSeconds > 0 ? `До старта: ${leftSeconds}` : 'Старт!';
    if (leftSeconds <= 0) clearInterval(localTimer);
  }, 1000);
}

function startQuestionTimer() {
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
    const crown = p.is_captain ? ' 👑' : '';
    li.textContent = `${p.name}${p.is_host ? ' (ведущий)' : ''}${crown}`;
    if (p.team === 'A') {
      li.className = 'team-a';
      teamAList.appendChild(li);
    } else if (p.team === 'B') {
      li.className = 'team-b';
      teamBList.appendChild(li);
    }
  });
}

function renderAnswers(options, canAnswer, canVote) {
  answersEl.innerHTML = '';
  options.forEach((option, idx) => {
    const row = document.createElement('div');
    row.className = 'answer-row';

    const voteBtn = document.createElement('button');
    voteBtn.className = 'secondary';
    voteBtn.textContent = `Голос: ${idx + 1}) ${option}`;
    voteBtn.disabled = !canVote;
    voteBtn.addEventListener('click', () => ws.send(JSON.stringify({ action: 'vote', choice: String(idx + 1) })));

    const answerBtn = document.createElement('button');
    answerBtn.textContent = `Ответ: ${idx + 1}) ${option}`;
    answerBtn.disabled = !canAnswer;
    answerBtn.addEventListener('click', () => ws.send(JSON.stringify({ action: 'answer', option_index: idx + 1 })));

    row.appendChild(voteBtn);
    row.appendChild(answerBtn);
    answersEl.appendChild(row);
  });

  const skipVoteBtn = document.createElement('button');
  skipVoteBtn.className = 'secondary';
  skipVoteBtn.textContent = 'Голосовать за пропуск';
  skipVoteBtn.disabled = !canVote;
  skipVoteBtn.onclick = () => ws.send(JSON.stringify({ action: 'vote', choice: 'skip' }));
  answersEl.appendChild(skipVoteBtn);

  const skipBtn = document.createElement('button');
  skipBtn.textContent = 'Пропустить вопрос (капитан)';
  skipBtn.disabled = !canAnswer;
  skipBtn.onclick = () => ws.send(JSON.stringify({ action: 'skip' }));
  answersEl.appendChild(skipBtn);
}

function renderVotes(votePercentages) {
  const entries = Object.entries(votePercentages || {});
  if (entries.length === 0) {
    voteStatsEl.textContent = '';
    return;
  }
  voteStatsEl.textContent = entries.map(([choice, pct]) => `${choice === 'skip' ? 'Пропуск' : `Вариант ${choice}`}: ${pct}%`).join(' | ');
}

function downloadResults(state) {
  const text = [
    `Игра ${state.pin}`,
    `Тема: ${state.topic}`,
    `Сложность: ${state.difficulty}`,
    `Счёт: Красные ${state.score_a} : Синие ${state.score_b}`,
    `Победитель: ${state.winner === 'draw' ? 'Ничья' : state.winner === 'A' ? 'Красные' : 'Синие'}`,
    `Статистика красных: ${JSON.stringify(state.team_stats.A)}`,
    `Статистика синих: ${JSON.stringify(state.team_stats.B)}`,
  ].join('\n');
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `quizbattle-${state.pin}.txt`;
  a.click();
}

function renderState(state) {
  latestState = state;
  topicEl.textContent = `Тема: ${state.topic} (${state.difficulty})`;
  scoreA.textContent = state.score_a;
  scoreB.textContent = state.score_b;
  renderTeams(state.players);
  renderVotes(state.vote_percentages);

  const me = state.players.find((p) => p.id === player.player_id);
  const teamName = state.current_team === 'A' ? 'красная' : 'синяя';

  if (state.status === 'waiting') {
    turnEl.textContent = 'Период подключения: ждём участников';
    qText.textContent = `PIN комнаты: ${state.pin}. Команды будут назначены случайно после старта.`;
    answersEl.innerHTML = '';
    timerEl.textContent = '';
    if (me && me.is_host) startBtn.classList.remove('hidden');
  } else if (state.phase === 'countdown') {
    startBtn.classList.add('hidden');
    turnEl.textContent = 'Игра запускается...';
    qText.textContent = 'Приготовьтесь!';
    answersEl.innerHTML = '';
    startCountdown(state.countdown_seconds || 3);
  } else if (state.status === 'in_progress') {
    startBtn.classList.add('hidden');
    turnEl.textContent = `Сейчас отвечает ${teamName} команда`;
    if (state.current_question) {
      qTitle.textContent = `Раунд ${state.current_question.order_index + 1}`;
      qText.textContent = state.current_question.text;
      const canVote = me && me.team === state.current_team;
      const canAnswer = canVote && me.is_captain;
      renderAnswers(state.current_question.options, canAnswer, canVote);
      if (currentQuestionId !== state.current_question.id) {
        currentQuestionId = state.current_question.id;
        resultEl.textContent = '';
        startQuestionTimer();
      }
    }
  } else {
    turnEl.textContent = 'Игра завершена';
    clearInterval(localTimer);
    timerEl.textContent = '';
    answersEl.innerHTML = '';
    saveResultsBtn.classList.remove('hidden');
    qText.textContent = state.winner === 'draw' ? 'Ничья! Отличная игра.' : `Победила ${state.winner === 'A' ? 'красная' : 'синяя'} команда!`;
    resultEl.textContent = `Красные: ${JSON.stringify(state.team_stats.A)} | Синие: ${JSON.stringify(state.team_stats.B)}`;
  }
}

startBtn.addEventListener('click', async () => {
  startBtn.disabled = true;
  try {
    const res = await fetch(`/games/${pin}/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ host_player_id: player.player_id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось стартовать');
  } catch (err) {
    resultEl.textContent = err.message;
    startBtn.disabled = false;
  }
});

saveResultsBtn.addEventListener('click', () => {
  if (latestState) downloadResults(latestState);
});

function connect() {
  ws = new WebSocket(wsUrl(`/ws/${pin}/${player.player_id}`));
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state') renderState(msg.data);
    if (msg.type === 'answer_result') {
      if (msg.data.timeout) resultEl.textContent = 'Время вышло';
      else if (msg.data.skip) resultEl.textContent = 'Вопрос пропущен';
      else resultEl.textContent = msg.data.correct ? 'Верно!' : `Неверно. Правильный ответ: ${msg.data.correct_option}`;
    }
  };
  ws.onclose = () => setTimeout(connect, 2000);
}

connect();

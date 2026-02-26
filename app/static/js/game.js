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
const captainControlsEl = document.getElementById('captain-controls');
const restartControlsEl = document.getElementById('restart-controls');
const restartTopicEl = document.getElementById('restart-topic');
const restartDifficultyEl = document.getElementById('restart-difficulty');
const restartBtn = document.getElementById('restart-btn');

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

function renderTeams(players, me) {
  teamAList.innerHTML = '';
  teamBList.innerHTML = '';
  captainControlsEl.innerHTML = '';

  const myTeam = me ? me.team : null;
  const isCaptain = Boolean(me && me.is_captain && myTeam);

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

    if (isCaptain && p.team === myTeam && p.id !== me.id && !p.is_captain) {
      const btn = document.createElement('button');
      btn.className = 'secondary';
      btn.textContent = `Передать корону: ${p.name}`;
      btn.onclick = () => ws.send(JSON.stringify({ action: 'transfer_captain', to_player_id: p.id }));
      captainControlsEl.appendChild(btn);
    }
  });

  if (!isCaptain || captainControlsEl.childElementCount === 0) {
    captainControlsEl.textContent = '';
  }
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
    row.appendChild(voteBtn);

    if (canAnswer) {
      const answerBtn = document.createElement('button');
      answerBtn.textContent = `Ответ: ${idx + 1}) ${option}`;
      answerBtn.disabled = false;
      answerBtn.addEventListener('click', () => ws.send(JSON.stringify({ action: 'answer', option_index: idx + 1 })));
      row.appendChild(answerBtn);
    }

    answersEl.appendChild(row);
  });

  const skipVoteBtn = document.createElement('button');
  skipVoteBtn.className = 'secondary';
  skipVoteBtn.textContent = 'Голосовать за пропуск';
  skipVoteBtn.disabled = !canVote;
  skipVoteBtn.onclick = () => ws.send(JSON.stringify({ action: 'vote', choice: 'skip' }));
  answersEl.appendChild(skipVoteBtn);

  if (canAnswer) {
    const skipBtn = document.createElement('button');
    skipBtn.textContent = 'Пропустить вопрос (капитан)';
    skipBtn.disabled = false;
    skipBtn.onclick = () => ws.send(JSON.stringify({ action: 'skip' }));
    answersEl.appendChild(skipBtn);
  }
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
  const winner = state.winner === 'draw' ? 'Ничья' : state.winner === 'A' ? 'Красная команда' : 'Синяя команда';
  const rows = [
    '===========================================',
    `             QUIZBATTLE REPORT             `,
    '===========================================',
    `Комната: ${state.pin}`,
    `Тема: ${state.topic}`,
    `Сложность: ${state.difficulty}`,
    `Итоговый счёт: Красные ${state.score_a} : Синие ${state.score_b}`,
    `Победитель: ${winner}`,
    '',
    'Состав команд:',
    `  Красные: ${state.players.filter((p) => p.team === 'A').map((p) => `${p.name}${p.is_captain ? ' 👑' : ''}`).join(', ') || '—'}`,
    `  Синие: ${state.players.filter((p) => p.team === 'B').map((p) => `${p.name}${p.is_captain ? ' 👑' : ''}`).join(', ') || '—'}`,
    '',
    'Командная статистика:',
    `  Красные: верно ${state.team_stats.A.correct}, неверно ${state.team_stats.A.incorrect}, таймаут ${state.team_stats.A.timeout}, бонус скорости +${state.team_stats.A.speed_bonus}`,
    `  Синие:   верно ${state.team_stats.B.correct}, неверно ${state.team_stats.B.incorrect}, таймаут ${state.team_stats.B.timeout}, бонус скорости +${state.team_stats.B.speed_bonus}`,
    '===========================================',
  ];
  const blob = new Blob([rows.join('\n')], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `quizbattle-result-${state.pin}.txt`;
  a.click();
}

function renderState(state) {
  latestState = state;
  topicEl.textContent = `Тема: ${state.topic} (${state.difficulty})`;
  scoreA.textContent = state.score_a;
  scoreB.textContent = state.score_b;
  const me = state.players.find((p) => p.id === player.player_id);
  renderTeams(state.players, me);
  renderVotes(state.vote_percentages);

  const teamName = state.current_team === 'A' ? 'красная' : 'синяя';

  if (state.status === 'waiting') {
    turnEl.textContent = 'Период подключения: ждём участников';
    qText.textContent = `PIN комнаты: ${state.pin}. Команды будут назначены случайно после старта.`;
    answersEl.innerHTML = '';
    timerEl.textContent = '';
    if (me && me.is_host) startBtn.classList.remove('hidden');
    restartControlsEl.classList.add('hidden');
  } else if (state.phase === 'countdown') {
    restartControlsEl.classList.add('hidden');
    startBtn.classList.add('hidden');
    turnEl.textContent = 'Игра запускается...';
    qText.textContent = 'Приготовьтесь!';
    answersEl.innerHTML = '';
    startCountdown(state.countdown_seconds || 3);
  } else if (state.status === 'in_progress') {
    restartControlsEl.classList.add('hidden');
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
    if (me && me.is_host) restartControlsEl.classList.remove('hidden');
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

restartBtn.addEventListener('click', () => {
  if (!restartTopicEl.value.trim()) {
    resultEl.textContent = 'Введите новую тему для следующей игры';
    return;
  }
  ws.send(JSON.stringify({
    action: 'host_control',
    control_action: 'restart',
    topic: restartTopicEl.value.trim(),
    difficulty: restartDifficultyEl.value,
  }));
  restartControlsEl.classList.add('hidden');
  resultEl.textContent = 'Запускаем новый матч...';
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

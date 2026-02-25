const form = document.getElementById('login-form');
const msg = document.getElementById('login-msg');

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  msg.textContent = 'Входим...';
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || 'Ошибка входа');
    localStorage.setItem('qb_user', JSON.stringify(body));
    window.location.href = '/';
  } catch (err) {
    msg.textContent = err.message;
  }
});

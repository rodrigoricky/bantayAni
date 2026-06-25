export function saveToken(token) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token);
  }
}

export function getToken() {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token');
  }
  return null;
}

const MUNICIPALITY_ALIASES = {
  'bukidnon-kibawe': 'camarines-naga',
  'camsur-naga': 'camarines-naga',
};

function migrateUser(user) {
  if (!user) return user;
  const munId = MUNICIPALITY_ALIASES[user.municipality_id] || user.municipality_id;
  if (munId !== user.municipality_id) {
    return { ...user, municipality_id: munId };
  }
  return user;
}

export function saveUser(user) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('user', JSON.stringify(migrateUser(user)));
  }
}

export function getUser() {
  if (typeof window !== 'undefined') {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const user = migrateUser(JSON.parse(raw));
    if (user.municipality_id !== JSON.parse(raw).municipality_id) {
      localStorage.setItem('user', JSON.stringify(user));
    }
    return user;
  }
  return null;
}

export function logout() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('bantay_ani_chat_history');
    localStorage.removeItem('bantayani_chat_history');
    localStorage.removeItem('bantay_ani_chat_rate');
    localStorage.removeItem('bantay_ani_chat_user');
  }
}

export function isAuthenticated() {
  return !!getToken() && !!getUser();
}
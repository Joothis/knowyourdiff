const loadUser = async (id) => {
  try {
    const res = await fetch(`/api/users/${id}`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
};

module.exports = { loadUser };

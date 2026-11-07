const loadUser = async (id) => {
  const res = await fetch(`/api/users/${id}`);
  return res.json();
};

module.exports = { loadUser };

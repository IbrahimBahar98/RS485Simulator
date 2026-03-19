const express = require('express');
const healthRoutes = require('./routes/health');

const app = express();

app.use(express.json());

app.use('/health', healthRoutes);

app.get('/api/status', (req, res) => {
  res.json({ status: 'ok' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

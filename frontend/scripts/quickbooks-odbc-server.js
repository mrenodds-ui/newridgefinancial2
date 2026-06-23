// Node.js ODBC QuickBooks integration for the frontend
// This script provides a local API for the React app to query QuickBooks via QODBC
// Requires: npm install odbc express cors

const express = require('express');
const odbc = require('odbc');
const cors = require('cors');

const app = express();
const port = 3030;
const DSN = process.env.QUICKBOOKS_DSN || 'QuickBooks Data QRemote';

app.use(cors());
app.use(express.json());

app.get('/quickbooks/odbc', async (req, res) => {
  const sql = req.query.sql;
  if (!sql) return res.status(400).json({ error: 'Missing sql parameter' });
  try {
    const connection = await odbc.connect(`DSN=${DSN}`);
    const result = await connection.query(sql);
    await connection.close();
    res.json({ results: result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/quickbooks/odbc/csv', async (req, res) => {
  const sql = req.query.sql;
  if (!sql) return res.status(400).send('Missing sql parameter');
  try {
    const connection = await odbc.connect(`DSN=${DSN}`);
    const result = await connection.query(sql);
    await connection.close();
    if (!result.length) return res.send('No data found\n');
    const fields = Object.keys(result[0]);
    const csv = [fields.join(','), ...result.map(row => fields.map(f => JSON.stringify(row[f] ?? '')).join(','))].join('\n');
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=quickbooks_export.csv');
    res.send(csv);
  } catch (err) {
    res.status(500).send('Error: ' + err.message);
  }
});

app.listen(port, () => {
  console.log(`QuickBooks ODBC local API listening at http://localhost:${port}`);
});

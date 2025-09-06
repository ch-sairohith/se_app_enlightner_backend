// server.js

import express from "express";
import dotenv from "dotenv";
import cors from "cors";
import {
  getGitaAnswer,
  getQuranAnswer,
  getComparativeAnswer,
  getBibleAnswer
} from "./gemini.js";

dotenv.config();
const app = express();
app.use(cors());
app.use(express.json());

app.post("/ask/all", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.status(400).json({ error: "Question is required" });

  try {
    const result = await getComparativeAnswer(question);
    res.json(result);
  } catch (err) {
    console.error("Error handling /ask/all:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/ask/gita", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.status(400).json({ error: "Question is required" });

  try {
    const result = await getGitaAnswer(question);
    res.json(result);
  } catch (err) {
    console.error("Error handling /ask/gita:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/ask/quran", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.status(400).json({ error: "Question is required" });

  try {
    const result = await getQuranAnswer(question);
    res.json(result);
  } catch (err) {
    console.error("Error handling /ask/quran:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
app.post("/ask/bible", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.status(400).json({ error: "Question is required" });

  try {
    const result = await getBibleAnswer(question);
    res.json(result);
  } catch (err) {
    console.error("Error handling /ask/bible:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});


app.get("/hi",(req,res)=>{
  res.send("hi!!!!")
})

const PORT = process.env.PORT || 5000;
app.listen(PORT, "0.0.0.0", () =>
  console.log(`✅ Server is running on port ${PORT}`)
);
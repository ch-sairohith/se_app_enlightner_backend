// gemini.js

import { GoogleGenerativeAI } from "@google/generative-ai";
import { firestore } from "./firestore.js";
import dotenv from "dotenv";

dotenv.config();
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

async function getRelevantVerses(question, book) {
  const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

  const idFormat = book === 'gita' 
    ? "gita_chapter_<chapter_number>_verse_<verse_number>"
    : "quran_chapter_<chapter_number>verse<chapter_number>_<verse_number>";
  const exampleId = book === 'gita'
    ? `["gita_chapter_2_verse_11", "gita_chapter_4_verse_7"]`
    : `["quran_chapter_2verse2_255", "quran_chapter_102verse102_8"]`;
  
  const bookName = book === 'gita' ? "Bhagavad Gita" : "Holy Quran";

  const prompt = `
  You are an assistant that finds relevant verses from the ${bookName}.
  The verse IDs are formatted like this: ${idFormat}.
  **IMPORTANT RULES:**
  1. If the user's question is NOT about the teachings, stories, or concepts within the ${bookName}, you MUST return an empty array.
  2. If the user's question is about the religion which holy book is ${bookName} then,you Must return an empty array. 
  3. For example, if the user asks about "Virat Kohli" or any other modern celebriety or any trash not about the relevent one  or a topic from a different religion, it is irrelevant.
  User question: "${question}"

  Return ONLY a JSON object with key "verses" and an array of the top 3-5 most relevant verse IDsIf the question is irrelevant, the array should be empty.
  Do not include any explanation or extra text.
   Example:
  {
    "verses": ${exampleId}
  }
  `;

  const result = await model.generateContent(prompt);
  let text = result.response.text().trim();
  console.log(text);
  text = text.replace(/```json/g, "").replace(/```/g, "").trim();

  try {
   // console.log(text);
    return JSON.parse(text);
  } catch (err) {
    console.error(`❌ Failed to parse Gemini response for ${bookName}:`, text);
    return { verses: [] };
  }
}

async function fetchVersesFromFirestore(verseIds) {
  const promises = verseIds.map(id => firestore.getVerseById(id));
  const verses = await Promise.all(promises);
  return verses.filter(v => v !== null);
}

async function analyzeSingleBook(question, verses, bookName) {
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
    const formattedVerses = verses.map(v => `📖 ${v.chapter}:${v.verse}\n${v.meaning}`).join("\n\n");
  
    const prompt =`
You are an assistant that explains teachings from the ${bookName}.

**CRITICAL FORMATTING RULES:**
1.  Your entire response MUST be plain text. Do not use any markdown like asterisks (*) for bolding or emphasis.
2.  The main title and the title of each numbered point must be enclosed in double quotes.
3.  The summary must be a numbered list, which is a strict rule.
4.  Follow the exact structure shown in the example below.

**CONTENT RULES (Follow in this order):**
1.  **Filter Gibberish & Irrelevance First:** If the user's question is nonsensical gibberish (e.g., "sbsjbf"), an irrelevant topic (e.g., "Virat Kohli," a different religion), or asks for a comparison, you MUST return an empty array.
2.  **Handle Keywords Next:** If the question is a single, meaningful keyword (e.g., 'life', 'karma', 'birth'), expand it into a full topic. For example, treat 'life' as 'What are the teachings about life?'.
3.  **Answer Full Questions:** If the question is a full, relevant question, provide a comprehensive answer.
4.  **Other Rules:** You can answer questions about characters within the ${bookName}, but do not answer ambiguous questions.

**EXAMPLE OF THE REQUIRED FORMAT:**
"Main Title of the Explanation"

This is an introductory paragraph explaining the overall concept.

1.  "Title for Point One": This is the detailed text for the first point.
2.  "Title for Point Two": This is the detailed text for the second point.



---
User question: "${question}"

Relevant verses:
${formattedVerses || "No verses found in DB. Please use your own knowledge."}

Provide a comprehensive explanation based on the question and the verses, strictly following all rules provided above.
`;
  
    const result = await model.generateContent(prompt);
    return result.response.text().trim();
}


async function analyzeComparatively(question, gitaData, quranData) {
  const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

  const prompt = `
  **CRITICAL RULE:** Your primary task is to determine if the user's question, "${question}", is directly related to the teachings, stories, or concepts within the religious texts of Hinduism (Bhagavad Gita), Islam (Quran), or Christianity (Bible).
  
  If the question is about a modern political figure (like Narendra Modi), a celebrity, sports, or any other topic NOT found in these ancient scriptures, you MUST IGNORE all other instructions and respond ONLY with the following JSON object:
  {
    "error": "This question does not seem to be related to the holy books."
  }
  
  If the question IS relevant, then proceed with the following task:
  
  Generate a detailed, multi-layered JSON response with the following structure:
  - "topic": A short title for the user's question.
  - "commonGround": A list of 5 single-word universal themes.
  - "results": An array for each religion (Hinduism, Islam, and Christianity).
    - Each religion object must contain: "religion", "overallSummary", "perspectives" (with "perspectiveName", "summary", "adherencePercentage"), and "sharedConcepts".

  BHAGAVAD GITA DATA:
  ${gitaData.length > 0 ? JSON.stringify(gitaData, null, 2) : "No specific verses found. Please use your general knowledge of the Bhagavad Gita."}

  QURAN DATA:
  ${quranData.length > 0 ? JSON.stringify(quranData, null, 2) : "No specific verses found. Please use your general knowledge of the Quran."}
  
  BIBLE DATA:
  No specific verses found. Please use your general knowledge of the Bible to answer for Christianity.

  Respond with ONLY the raw JSON object, without any markdown or extra text.
  `;

  const result = await model.generateContent(prompt);
  let text = result.response.text().trim();
  text = text.replace(/```json/g, " ").replace(/```/g, "").trim();

  try {
    return JSON.parse(text);
  } catch (err) {
    console.error("❌ Failed to parse final comparative response:", text);
    return { error: "Failed to generate a comparative analysis." };
  }
}

export async function getGitaAnswer(question) {
  const { verses: verseIds } = await getRelevantVerses(question, 'gita');
  const verses = await fetchVersesFromFirestore(verseIds);
  const summary = await analyzeSingleBook(question, verses, "Bhagavad Gita");
  return { scripture: "Bhagavad Gita", question, summary };
}

export async function getQuranAnswer(question) {
    const { verses: verseIds } = await getRelevantVerses(question, 'quran');
    const verses = await fetchVersesFromFirestore(verseIds);
    const summary = await analyzeSingleBook(question, verses, "Quran");
    
    return { scripture: "Quran", question, summary };
}
export async function getBibleAnswer(question) {
  const summary = await analyzeSingleBook(question, [], "Bible");
  return { scripture: "Bible", question, summary };
}

export async function getComparativeAnswer(question) {
  console.log(`Starting comparative analysis for: "${question}"`);

  const [gitaVerseIdsResult, quranVerseIdsResult] = await Promise.all([
    getRelevantVerses(question, 'gita'),
    getRelevantVerses(question, 'quran')
  ]);

  const allVerseIds = [
      ...gitaVerseIdsResult.verses,
      ...quranVerseIdsResult.verses
  ];
  
  const allVerses = await fetchVersesFromFirestore(allVerseIds);

  const gitaVerses = allVerses.filter(v => v.religion === 'hinduism');
  const quranVerses = allVerses.filter(v => v.religion === 'Islam');

  console.log(`Fetched ${gitaVerses.length} Gita verses and ${quranVerses.length} Quran verses.`);
  const finalResponse = await analyzeComparatively(question, gitaVerses, quranVerses);

  return finalResponse;
}
const prompt = process.argv[2] || await readStdin();
console.log(JSON.stringify({ message: `fixture:${prompt.slice(-20)}` }));
async function readStdin() { const chunks=[]; for await (const chunk of process.stdin) chunks.push(chunk); return Buffer.concat(chunks).toString('utf8'); }

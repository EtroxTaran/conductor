export function App() {
  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Welcome to {{PROJECT_NAME}}</h1>
      <p>An Nx full-stack application with React and Node.js</p>
      <ul>
        <li>Frontend: React 19 + Vite</li>
        <li>Backend: Hono + Prisma</li>
        <li>Monorepo: Nx</li>
      </ul>
    </div>
  );
}

export default App;

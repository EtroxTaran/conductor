// Shared UI components
// Add React components here that can be used by any frontend app

export function Button({
  children,
  onClick,
  variant = 'primary',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
}) {
  const styles = {
    primary: {
      backgroundColor: '#0066cc',
      color: 'white',
    },
    secondary: {
      backgroundColor: '#f0f0f0',
      color: '#333',
    },
  };

  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 16px',
        borderRadius: '4px',
        border: 'none',
        cursor: 'pointer',
        fontFamily: 'system-ui, sans-serif',
        ...styles[variant],
      }}
    >
      {children}
    </button>
  );
}

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

// Example test file - replace with actual component tests
describe('Example Test', () => {
  it('renders correctly', () => {
    render(<div data-testid="test">Hello</div>);
    expect(screen.getByTestId('test')).toHaveTextContent('Hello');
  });
});

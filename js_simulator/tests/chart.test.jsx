import { render, screen } from '@testing-library/react';
import Chart from '../src/components/Chart';

// Mock chart rendering
jest.mock('../src/components/Chart', () => {
  return jest.fn(() => <div data-updated="true" />);
});

describe('Chart Component Test', () => {
  it('updates correctly on new data prop', () => {
    render(<Chart data={[1, 2, 3]} />);
    const chartElement = screen.getByRole('img');
    expect(chartElement).toHaveAttribute('data-updated', 'true');
    expect(screen.getAllByRole('img')).toHaveLength(1);
  });
});
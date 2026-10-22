import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Allow async UI transitions to finish on slower Windows test machines.
configure({ asyncUtilTimeout: 5000 });

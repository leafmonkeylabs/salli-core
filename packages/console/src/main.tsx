/**
 * The open console: `createConsole()` with no extensions, built and served
 * by the Salli server at /console. An edition builds its own entry like
 * this one, passing its extensions.
 */
import './styles/index.css';
import { createConsole } from './console';
import { applyTheme, storedTheme } from './preferences';

applyTheme(storedTheme());
const root = document.getElementById('root');
if (root) createConsole().mount(root);

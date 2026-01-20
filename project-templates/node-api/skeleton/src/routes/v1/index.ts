import { Hono } from 'hono';
import users from './users.js';

const v1 = new Hono();

v1.route('/users', users);

export default v1;

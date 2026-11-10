import { testIssue } from '../src/test';

describe('Test Issue', () => {
  it('should return resolved message', () => {
    expect(testIssue()).toBe("test issue resolved");
  });
});

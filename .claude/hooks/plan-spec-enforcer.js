/**
 * PostToolUse hook: enforce spec-only constraint on plan writes.
 * Blocks Opus from writing implementation plans to plans/* directory.
 *
 * Red flags (trigger block):
 * - File exceeds 100 lines
 * - Contains code block > 5 lines
 * - Contains "old_string" or "new_string"
 * - Contains numbered step sequences (Step 1:, Step 2:, etc)
 * - Contains "replace entire file"
 */

function validatePlanSpec(content) {
  const lines = content.split('\n');

  // Check line count
  if (lines.length > 100) {
    return {
      valid: false,
      reason: 'Plan exceeds 100 lines. Specs only (files + functions + decisions + why). Implementation is Haiku\'s job.'
    };
  }

  // Check for code blocks > 5 lines
  let inCodeBlock = false;
  let codeBlockLines = 0;
  for (const line of lines) {
    if (line.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      codeBlockLines = 0;
    } else if (inCodeBlock) {
      codeBlockLines++;
      if (codeBlockLines > 5) {
        return {
          valid: false,
          reason: 'Code block exceeds 5 lines. Specs contain only skeleton signatures and short examples.'
        };
      }
    }
  }

  // Check for red flag strings
  const redFlags = [
    { pattern: /old_string|new_string/, msg: 'Contains old_string/new_string. That\'s implementation, not spec.' },
    { pattern: /^Step\s+\d+:/, msg: 'Numbered step sequences. Specs are files + functions + decisions, not prescriptive procedures.' },
    { pattern: /replace entire file/, msg: 'Prescriptive "replace entire file" instruction. That\'s implementation.' }
  ];

  for (const { pattern, msg } of redFlags) {
    if (pattern.test(content)) {
      return { valid: false, reason: msg };
    }
  }

  return { valid: true };
}

module.exports = {
  id: 'plan-spec-enforcer',
  type: 'PostToolUse',
  when: (call) => {
    return call.tool === 'Write' && call.arguments.file_path?.includes('/plans/');
  },
  async handle(call, { ask, deny, allow }) {
    const validation = validatePlanSpec(call.arguments.content);

    if (!validation.valid) {
      return deny(`CLAUDE.md violation: ${validation.reason}`);
    }

    return allow();
  }
};

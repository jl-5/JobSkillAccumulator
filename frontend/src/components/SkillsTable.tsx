import { Fragment, useState } from "react";
import type { SkillCount } from "../types";

interface Props {
  skills: SkillCount[];
}

export function SkillsTable({ skills }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (skills.length === 0) {
    return <p className="empty-state">No skills were extracted from these postings.</p>;
  }

  function toggle(skill: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(skill)) {
        next.delete(skill);
      } else {
        next.add(skill);
      }
      return next;
    });
  }

  return (
    <table className="skills-table">
      <thead>
        <tr>
          <th scope="col" className="rank-col">
            Rank
          </th>
          <th scope="col">Skill</th>
          <th scope="col" className="num-col">
            Mentions
          </th>
          <th scope="col" className="pct-col">
            % of Postings
          </th>
        </tr>
      </thead>
      <tbody>
        {skills.map((skill, i) => {
          const isExpanded = expanded.has(skill.skill);
          const hasPostings = skill.postings.length > 0;
          return (
            <Fragment key={skill.skill}>
              <tr>
                <td className="rank-col">{i + 1}</td>
                <td>
                  {hasPostings ? (
                    <button
                      type="button"
                      className="skill-name-toggle"
                      aria-expanded={isExpanded}
                      onClick={() => toggle(skill.skill)}
                    >
                      <span className="skill-toggle-chevron">{isExpanded ? "▾" : "▸"}</span>
                      {skill.skill}
                    </button>
                  ) : (
                    skill.skill
                  )}
                </td>
                <td className="num-col">{skill.count}</td>
                <td className="pct-col">
                  <div className="pct-cell">
                    <div className="pct-bar-track">
                      <div className="pct-bar-fill" style={{ width: `${skill.percentage}%` }} />
                    </div>
                    <span>{skill.percentage}%</span>
                  </div>
                </td>
              </tr>
              {isExpanded && hasPostings && (
                <tr className="postings-row">
                  <td />
                  <td colSpan={3}>
                    <ul className="postings-list">
                      {skill.postings.map((posting, j) => (
                        <li key={j}>
                          {posting.url ? (
                            <a href={posting.url} target="_blank" rel="noopener noreferrer">
                              {posting.title}
                            </a>
                          ) : (
                            <span>{posting.title}</span>
                          )}
                          {posting.company && <span className="posting-company"> @ {posting.company}</span>}
                          <span className="posting-source"> · {posting.source}</span>
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

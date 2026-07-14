import React from 'react';
import type { JobPosting } from '../api';
import { ExternalLink, Building2, MapPin, Calendar } from 'lucide-react';

interface JobTableProps {
  jobs: JobPosting[];
}

export const JobTable: React.FC<JobTableProps> = ({ jobs }) => {
  if (jobs.length === 0) {
    return (
      <div className="glass-panel" style={{ textAlign: 'center', padding: '40px' }}>
        <p style={{ color: 'var(--text-secondary)' }}>No jobs found matching criteria.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel table-container" style={{ padding: 0, overflow: 'hidden' }}>
      <table>
        <thead>
          <tr>
            <th>Role & Company</th>
            <th>Location</th>
            <th>Source & Tags</th>
            <th>Posted</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.id}>
              <td>
                <div className="job-title">{job.title}</div>
                <div className="job-company">
                  <Building2 size={14} />
                  {job.company}
                </div>
              </td>
              <td>
                <div className="job-company">
                  <MapPin size={14} />
                  {job.location}
                </div>
              </td>
              <td>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  <span className="tag tag-source">{job.source}</span>
                  {job.tags && job.tags.filter(t => t !== job.source).map(tag => (
                    <span key={tag} className="tag">{tag}</span>
                  ))}
                </div>
              </td>
              <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Calendar size={14} />
                  {job.posting_date || new Date(job.scraped_at).toISOString().split('T')[0]}
                </div>
              </td>
              <td>
                <a href={job.url} target="_blank" rel="noreferrer" className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                  Apply <ExternalLink size={14} />
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

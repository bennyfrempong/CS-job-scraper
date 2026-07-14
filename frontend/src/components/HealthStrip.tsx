import React from 'react';
import type { SourceStats } from '../api';
import { Activity, CheckCircle2, AlertCircle } from 'lucide-react';

interface HealthStripProps {
  sources: SourceStats[];
}

export const HealthStrip: React.FC<HealthStripProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="health-strip">
      {sources.map(source => {
        let statusClass = 'status-dot ';
        let Icon = Activity;
        
        if (source.status === 'success') {
          statusClass += 'status-success';
          Icon = CheckCircle2;
        } else if (source.status === 'error') {
          statusClass += 'status-error';
          Icon = AlertCircle;
        } else {
          statusClass += 'status-running';
        }

        return (
          <div key={source.source} className="health-badge" title={`Last run: ${source.completed_at || 'Running'}\nErrors: ${source.error_count || 0}`}>
            <div className={statusClass} />
            <Icon size={14} />
            <span>{source.source}</span>
          </div>
        );
      })}
    </div>
  );
};

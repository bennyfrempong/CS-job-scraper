import React from 'react';
import type { DashboardStats } from '../api';

interface StatCardsProps {
  stats: DashboardStats;
}

export const StatCards: React.FC<StatCardsProps> = ({ stats }) => {
  return (
    <div className="stats-grid">
      <div className="stat-card glass-panel">
        <div className="stat-label">Total Jobs Scraped</div>
        <div className="stat-value">{stats.total_postings.toLocaleString()}</div>
      </div>
      
      <div className="stat-card glass-panel">
        <div className="stat-label">Active Listings</div>
        <div className="stat-value" style={{ color: 'var(--success)' }}>
          {stats.active_postings.toLocaleString()}
        </div>
      </div>
      
      <div className="stat-card glass-panel">
        <div className="stat-label">Added Last 24h</div>
        <div className="stat-value" style={{ color: 'var(--accent-primary)' }}>
          +{stats.postings_last_24h.toLocaleString()}
        </div>
      </div>
    </div>
  );
};

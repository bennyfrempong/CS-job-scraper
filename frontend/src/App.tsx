import { useEffect, useState } from 'react';
import { fetchJobs, fetchStats, fetchSources } from './api';
import type { DashboardStats, SourceStats, PaginatedJobs } from './api';
import { StatCards } from './components/StatCards';
import { HealthStrip } from './components/HealthStrip';
import { JobTable } from './components/JobTable';
import { Search, Filter } from 'lucide-react';

function App() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [sources, setSources] = useState<SourceStats[]>([]);
  const [jobsData, setJobsData] = useState<PaginatedJobs | null>(null);
  
  // Filters
  const [search, setSearch] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadDashboardData = async () => {
    try {
      const [statsData, sourcesData] = await Promise.all([
        fetchStats(),
        fetchSources()
      ]);
      setStats(statsData);
      setSources(sourcesData);
    } catch (e) {
      console.error("Failed to load dashboard stats", e);
    }
  };

  const loadJobs = async () => {
    setLoading(true);
    try {
      const params: any = { offset: page * 50, limit: 50 };
      if (search) params.title = search; // simple search by title for now
      if (sourceFilter) params.source = sourceFilter;

      const data = await fetchJobs(params);
      setJobsData(data);
    } catch (e) {
      console.error("Failed to load jobs", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  useEffect(() => {
    // Debounce search slightly
    const timer = setTimeout(() => {
      loadJobs();
    }, 300);
    return () => clearTimeout(timer);
  }, [search, sourceFilter, page]);

  return (
    <div className="container">
      <header className="header">
        <h1>CS Pipeline Dashboard</h1>
        <p>Real-time aggregation and deduplication of CS internship postings.</p>
      </header>

      {sources.length > 0 && <HealthStrip sources={sources} />}
      
      {stats && <StatCards stats={stats} />}

      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div style={{ position: 'relative', flex: 2 }}>
            <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input 
              type="text" 
              className="input-glass" 
              placeholder="Search roles..." 
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              style={{ width: '100%', paddingLeft: '40px' }}
            />
          </div>
          <div style={{ position: 'relative', flex: 1 }}>
            <Filter size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <select 
              className="input-glass" 
              value={sourceFilter}
              onChange={(e) => { setSourceFilter(e.target.value); setPage(0); }}
              style={{ width: '100%', paddingLeft: '40px' }}
            >
              <option value="">All Sources</option>
              {stats?.postings_by_source && Object.keys(stats.postings_by_source).map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading && !jobsData ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>Loading postings...</div>
      ) : (
        <>
          {jobsData && <JobTable jobs={jobsData.results} />}
          
          {jobsData && jobsData.total > 50 && (
            <div className="pagination">
              <button 
                className="pagination-btn"
                disabled={page === 0} 
                onClick={() => setPage(p => Math.max(0, p - 1))}
              >
                Previous Page
              </button>
              <span className="page-info">
                Showing {page * 50 + 1}-{Math.min((page + 1) * 50, jobsData.total)} of {jobsData.total.toLocaleString()}
              </span>
              <button 
                className="pagination-btn"
                disabled={(page + 1) * 50 >= jobsData.total} 
                onClick={() => setPage(p => p + 1)}
              >
                Next Page
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;

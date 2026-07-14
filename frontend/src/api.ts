import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
});

export interface JobPosting {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  posting_date: string | null;
  scraped_at: string;
  tags: string[];
  is_active: boolean;
}

export interface PaginatedJobs {
  total: number;
  limit: number;
  offset: number;
  results: JobPosting[];
}

export interface SourceStats {
  source: string;
  status: string | null;
  started_at: string | null;
  completed_at: string | null;
  new_listings: number | null;
  skipped_dupes: number | null;
  error_count: number | null;
}

export interface DashboardStats {
  total_postings: number;
  active_postings: number;
  postings_last_24h: number;
  postings_by_source: Record<string, number>;
  last_run_at: string | null;
}

export const fetchJobs = async (params: any = {}) => {
  const { data } = await api.get<PaginatedJobs>('/postings', { params });
  return data;
};

export const fetchStats = async () => {
  const { data } = await api.get<DashboardStats>('/stats');
  return data;
};

export const fetchSources = async () => {
  const { data } = await api.get<SourceStats[]>('/sources');
  return data;
};

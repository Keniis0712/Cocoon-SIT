export interface PageResp<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NamedMetric {
  name: string;
  value: number;
}

export interface TimeSeriesPoint {
  bucket_start_at: string;
  value: number;
}

export interface RankedCocoonMetric {
  cocoon_id: string;
  cocoon_name: string;
  value: number;
}


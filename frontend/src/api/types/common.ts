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
  bucket: string;
  value: number;
}

export interface RankedCocoonMetric {
  cocoon_id: number;
  cocoon_name: string;
  value: number;
}


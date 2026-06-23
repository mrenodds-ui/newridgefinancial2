import React, { useEffect, useRef, useState } from "react";

import { buildHalChartFileUrl, fetchHalChartFileBlob } from "../api/client";

type HalChartPreviewProps = {
  path: string;
  alt: string;
  className?: string;
};

export function HalChartPreview({ path, alt, className }: HalChartPreviewProps) {
  const objectUrlRef = useRef<string | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError(null);
    setObjectUrl(null);

    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }

    fetchHalChartFileBlob(path)
      .then((blob) => {
        if (cancelled) {
          return;
        }
        try {
          const nextUrl = URL.createObjectURL(blob);
          objectUrlRef.current = nextUrl.startsWith("blob:") ? nextUrl : null;
          setObjectUrl(nextUrl);
        } catch {
          setObjectUrl(buildHalChartFileUrl(path));
        }
      })
      .catch((fetchError: unknown) => {
        if (cancelled) {
          return;
        }
        setError(fetchError instanceof Error ? fetchError.message : "Unable to load the rendered chart preview.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, []);

  if (loading) {
    return <div className="hal-answer-card__section">Loading chart preview...</div>;
  }

  if (error) {
    return <div className="hal-answer-card__section">{error}</div>;
  }

  if (!objectUrl) {
    return null;
  }

  return <img alt={alt} src={objectUrl} className={className} />;
}

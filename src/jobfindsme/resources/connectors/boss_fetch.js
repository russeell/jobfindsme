(async () => {
  const url = __API_URL__;
  try {
    const response = await fetch(url, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (response.status === 401 || response.status === 403) {
      return JSON.stringify({
        error: "authentication_required",
        status: response.status,
      });
    }
    if (!response.ok) {
      return JSON.stringify({ error: "http_error", status: response.status });
    }
    const data = await response.json();
    const jobs = ((data || {}).zpData || {}).jobList || [];
    return JSON.stringify({
      jobs: jobs.map((job) => ({
        job_id: job.encryptJobId || job.securityId || "",
        title: job.jobName || "",
        salary: job.salaryDesc || "",
        location: [job.cityName, job.areaDistrict, job.businessDistrict]
          .filter((value) => value && value !== "不限")
          .join(" · "),
        company: job.brandName || "",
        experience: job.jobExperience || "",
        degree: job.jobDegree || "",
        skills: (job.skills || []).join(", "),
        job_labels: (job.jobLabels || []).join(", "),
        boss_name: job.bossTitle || "",
        boss_active: job.activeTimeDesc || (job.bossOnline ? "在线" : ""),
        company_scale: job.brandScaleName || "",
        company_stage: job.brandStageName || "",
        company_industry: job.brandIndustry || "",
        welfare: (job.welfareList || []).join(", "),
        job_link: job.encryptJobId
          ? `https://www.zhipin.com/job_detail/${job.encryptJobId}.html`
          : "",
      })),
    });
  } catch (error) {
    return JSON.stringify({
      error: "network_error",
      message: String(error && error.message ? error.message : error),
    });
  }
})()
